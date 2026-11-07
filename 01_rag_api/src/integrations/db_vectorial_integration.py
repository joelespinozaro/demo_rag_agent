from abc import ABC, abstractmethod

from src.dto.busqueda_dto import ElementoBusqueda


class DbVectorialIntegration(ABC):
    @abstractmethod
    def search(self, vector: list[float], limit: int = 5, query_text: str | None = None) -> list[ElementoBusqueda]:
        """query_text es opcional: solo lo usan las implementaciones que tambien buscan por palabras (BM25)."""
        ...
