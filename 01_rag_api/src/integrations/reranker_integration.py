from abc import ABC, abstractmethod

from src.dto.busqueda_dto import ElementoBusqueda


class RerankerIntegration(ABC):
    @abstractmethod
    def rerank(self, question: str, candidates: list[ElementoBusqueda], top_k: int) -> list[ElementoBusqueda]:
        ...