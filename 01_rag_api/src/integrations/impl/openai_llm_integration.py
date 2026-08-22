from typing import List

from langchain_core.messages import BaseMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI

from src.dto.api_entities import LLMResponse
from src.integrations.impl.prompt import INSTRUCTIONS, USER_PROMPT
from src.integrations.llm_integration import LLMIntegration
from src.utils.environment import ASSISTANT_NAME, OPENAI_API_KEY, OPENAI_MODEL

class OpenAILlmIntegration(LLMIntegration):
    def __init__(self):
        self._llm = ChatOpenAI(api_key=OPENAI_API_KEY, model=OPENAI_MODEL)
        self._prompt = ChatPromptTemplate.from_messages(
            [
                ("system", INSTRUCTIONS),
                MessagesPlaceholder("history"),
                ("human", USER_PROMPT),
            ]
        )
        self._chain = self._prompt | self._llm

    def generate_response(self, question: str, context: str, history: List[BaseMessage]) -> LLMResponse:
        response = self._chain.invoke(
            {
                "assistant_name": ASSISTANT_NAME,
                "question": question,
                "context": context,
                "history": history,
            }
        )

        usage = response.usage_metadata or {}

        return LLMResponse(
            answer=response.content,
            input_tokens=usage.get("input_tokens", 0),
            output_tokens=usage.get("output_tokens", 0),
        )