from abc import ABC, abstractmethod

class QueryExpansionIntegration(ABC):
    @abstractmethod
    def expand(self, question: str, n: int) -> list[str]:
        ...