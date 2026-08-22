from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from src.dto.busqueda_dto import ElementoBusqueda
from src.integrations.impl.prompt import RERANK_INSTRUCTIONS, RERANK_USER_PROMPT
from src.integrations.reranker_integration import RerankerIntegration
from src.utils.environment import OPENAI_API_KEY, OPENAI_MODEL


class _RankedCandidate(BaseModel):
    index: int = Field(description="Indice del documento candidato, segun el orden en que fue listado")
    score: int = Field(description="Puntaje de relevancia del documento respecto a la pregunta, de 0 a 10")


class _RerankedResult(BaseModel):
    ranked: list[_RankedCandidate] = Field(description="Lista de candidatos puntuados por relevancia")


class OpenAIRerankerIntegration(RerankerIntegration):
    def __init__(self):
        llm = ChatOpenAI(api_key=OPENAI_API_KEY, model=OPENAI_MODEL, temperature=0)
        self._llm = llm.with_structured_output(_RerankedResult)
        self._prompt = ChatPromptTemplate.from_messages(
            [
                ("system", RERANK_INSTRUCTIONS),
                ("human", RERANK_USER_PROMPT),
            ]
        )
        self._chain = self._prompt | self._llm

    def rerank(self, question: str, candidates: list[ElementoBusqueda], top_k: int) -> list[ElementoBusqueda]:
        if not candidates:
            return []

        formatted_candidates = "\n".join(
            f"[{i}] {candidate.content}" for i, candidate in enumerate(candidates)
        )

        result: _RerankedResult = self._chain.invoke(
            {"question": question, "candidates": formatted_candidates}
        )

        scores_by_index = {ranked.index: ranked.score for ranked in result.ranked}

        ordered = sorted(
            range(len(candidates)),
            key=lambda i: scores_by_index.get(i, 0),
            reverse=True,
        )

        return [candidates[i] for i in ordered[:top_k]]