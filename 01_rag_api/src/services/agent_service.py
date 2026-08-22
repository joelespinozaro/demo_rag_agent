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
    RETRIEVAL_LIMIT
)
from src.utils.logger import get_logger
from src.integrations.db_vectorial_integration import DbVectorialIntegration
from src.integrations.embedding_integration import EmbeddingIntegration
from src.integrations.llm_integration import LLMIntegration

logger = get_logger(__name__)

class AgentService:
    def __init__(self, embedding: EmbeddingIntegration, dbVectorial: DbVectorialIntegration, llm:LLMIntegration, db: Session,) -> None:
        self._repo = HistoryRepository(db)
        self._embedding = embedding
        self._dbVectorial = dbVectorial
        self._llm = llm

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
        # Paso 1: Generar embedding de la pregunta
        vector = self._embedding.generate_embedding(question)
        # Paso 2: Buscar en la base de datos vectorial los documentos más relevantes
        contexts = self._dbVectorial.search(vector, limit=RETRIEVAL_LIMIT)
        formatted_contexts = "\n".join([f"- {ctx.content}" for ctx in contexts])

        # Paso 3: Inferir respuesta
        result = self._llm.generate_response(question, formatted_contexts, history_messages)
        retrieved_contexts = formatted_contexts

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
                "retrieved_contexts_count": len(retrieved_contexts or []),
            },
        )

        return {
            "user": user,
            "answer": result.answer,
            "session_id": session_id,
            "trace_id": trace_id,
        }

    
