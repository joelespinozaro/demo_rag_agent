from abc import ABC, abstractmethod


class EmbeddingIntegration(ABC):
    @abstractmethod
    def generate_embedding(self, text: str) -> list[float]:
        ...
