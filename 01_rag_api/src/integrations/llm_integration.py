
from typing import List
from langchain_core.messages import BaseMessage
from src.dto.api_entities import LLMResponse
from abc import ABC, abstractmethod

class LLMIntegration(ABC):
    @abstractmethod
    def generate_response(self,
            question: str, 
            context: str, 
            history: List[BaseMessage]
        ) -> LLMResponse:
        ...