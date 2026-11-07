import json
import time
from typing import List, Optional
import uuid

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from sqlalchemy.orm import Session

from src.services.prompt import INSTRUCTIONS
from src.repositories.history_repository import HistoryRepository
from src.repositories.models.history import History
from src.utils.environment import (
    HISTORY_LIMIT,
    RETRIEVAL_LIMIT,
    RETRIEVAL_CANDIDATES,
    QUERY_EXPANSION_COUNT,
    GRAPH_SEED_K,
)
from src.utils.logger import get_logger
from src.integrations.db_vectorial_integration import DbVectorialIntegration
from src.integrations.embedding_integration import EmbeddingIntegration
from src.integrations.llm_integration import LLMIntegration
from src.dto.busqueda_dto import ElementoBusqueda
from src.integrations.query_expansion_integration import QueryExpansionIntegration
from src.integrations.reranker_integration import RerankerIntegration
from src.integrations.graph_integration import GraphIntegration
from src.services.grounding import build_context, check_citations

logger = get_logger(__name__)

class AgentService:
    def __init__(
        self,
        db: Session,
        embedding: EmbeddingIntegration,
        dbVectorial: DbVectorialIntegration,
        llm_integration: LLMIntegration,
        query_expansion: QueryExpansionIntegration,
        reranker: RerankerIntegration,
        graph: Optional[GraphIntegration] = None,
    ) -> None:
            
        self._repo = HistoryRepository(db)
        self._embedding = embedding
        self._dbVectorial = dbVectorial
        self._llm = llm_integration
        self._query_expansion = query_expansion
        self._reranker = reranker
        self._graph = graph
                
    def _retrieve_with_query_expansion(self, question: str, question_vector: list[float]) -> tuple[list[ElementoBusqueda], int]:
        variants = self._query_expansion.expand(question, QUERY_EXPANSION_COUNT)
        queries = [question] + variants

        best_by_id: dict[str, ElementoBusqueda] = {}
        for query in queries:
            vector = question_vector if query == question else self._embedding.generate_embedding(query)
            for ctx in self._dbVectorial.search(vector, limit=RETRIEVAL_CANDIDATES, query_text=query):
                existing = best_by_id.get(ctx.id)
                if existing is None or ctx.score > existing.score:
                    best_by_id[ctx.id] = ctx

        merged = sorted(best_by_id.values(), key=lambda ctx: ctx.score, reverse=True)
        return merged[:RETRIEVAL_CANDIDATES], len(variants)
    
    def _rerank(self, question: str, candidates: list[ElementoBusqueda]) -> list[ElementoBusqueda]:
        return self._reranker.rerank(question, candidates, RETRIEVAL_LIMIT)

    async def chat(self, question: str, user: str, session_id: Optional[str]) -> dict:
        is_new_session = not session_id
        if is_new_session:
            logger.info("Creando nueva sesión")
            session_id = str(uuid.uuid4())

        trace_id = str(uuid.uuid4())

        logger.info(
            "Iniciando chat",
            extra={"session_id": session_id, "trace_id": trace_id, "user": user},
        )

        t0 = time.perf_counter()
        history_records = [] if is_new_session else self._repo.get_by_session_id(session_id, limit=HISTORY_LIMIT)
        t_history = time.perf_counter() - t0

        history_messages: List[BaseMessage] = []
        for record in history_records:
            history_messages.append(HumanMessage(content=record.question))
            history_messages.append(AIMessage(content=record.answer))

        t0 = time.perf_counter()
        # Implementar RAG
        # Paso 1 y 2: Expandir la pregunta en variantes y buscar documentos similares
        # para cada una, fusionando y deduplicando los resultados (query expansion).
        question_vector = self._embedding.generate_embedding(question)
        candidates, variants_count = self._retrieve_with_query_expansion(question, question_vector)

        # Paso 2b: GraphRAG (local search). Las fichas de entidad del grafo entran
        # como candidatos y compiten con los chunks en el reranking.
        graph_count = 0
        if self._graph is not None:
            fichas = self._graph.search(question_vector, k=GRAPH_SEED_K)
            graph_count = len(fichas)
            candidates = candidates + fichas

        # Paso 3: Reranking de los candidatos con el LLM, quedandonos con el top-k final.
        contexts = self._rerank(question, candidates)

        # Paso 4: Grounding. Cada contexto lleva un id citable: [C1] chunk, [G1] grafo.
        context_text, sources = build_context(contexts)

        # Paso 5: Inferir respuesta y validar que cada oracion cite su fuente.
        result = self._llm.generate_response(question, context_text, history_messages)
        grounding = check_citations(result.answer, {s["id"] for s in sources})
        retrieved_contexts = json.dumps(sources, ensure_ascii=False)

        t_agent = time.perf_counter() - t0

        t0 = time.perf_counter()
        self._repo.save(
            History(
                trace_id=trace_id,
                session_id=session_id,
                question=question,
                answer=result.answer,
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
                user=user,
                retrieved_contexts=retrieved_contexts,
            )
        )
        t_save = time.perf_counter() - t0

        logger.info(
            "Chat finalizado",
            extra={
                "trace_id": trace_id,
                "session_id": session_id,
                "t_history_ms": round(t_history * 1000, 2),
                "t_agent_ms": round(t_agent * 1000, 2),
                "t_save_ms": round(t_save * 1000, 2),
                "query_variants_count": variants_count,
                "retrieval_candidates_count": len(candidates),
                "retrieved_contexts_count": len(contexts),
                "graph_candidates_count": graph_count,
                "grounding_ratio": grounding["ratio"],
                "uncited_sentences": len(grounding["sin_cita"]),
            },
        )

        return {
            "user": user,
            "answer": result.answer,
            "session_id": session_id,
            "trace_id": trace_id,
            "sources": [
                {"id": s["id"], "tipo": s["tipo"], "source_file": s["source_file"], "extracto": s["content"][:240]}
                for s in sources
            ],
            "grounding": grounding,
        }

    
