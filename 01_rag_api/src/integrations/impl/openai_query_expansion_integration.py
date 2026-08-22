from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from src.integrations.impl.prompt import QUERY_EXPANSION_INSTRUCTIONS, QUERY_EXPANSION_USER_PROMPT
from src.integrations.query_expansion_integration import QueryExpansionIntegration
from src.utils.environment import OPENAI_API_KEY, OPENAI_MODEL


class _QueryVariants(BaseModel):
    variants: list[str] = Field(description="Lista de reformulaciones de la pregunta original")


class OpenAIQueryExpansionIntegration(QueryExpansionIntegration):
    def __init__(self):
        llm = ChatOpenAI(api_key=OPENAI_API_KEY, model=OPENAI_MODEL, temperature=0.7)
        self._llm = llm.with_structured_output(_QueryVariants)
        self._prompt = ChatPromptTemplate.from_messages(
            [
                ("system", QUERY_EXPANSION_INSTRUCTIONS),
                ("human", QUERY_EXPANSION_USER_PROMPT),
            ]
        )
        self._chain = self._prompt | self._llm

    def expand(self, question: str, n: int) -> list[str]:
        if n <= 0:
            return []

        result: _QueryVariants = self._chain.invoke({"question": question, "n": n})
        return result.variants[:n]