from abc import ABC, abstractmethod

from src.dto.busqueda_dto import ElementoBusqueda


class GraphIntegration(ABC):
    @abstractmethod
    def search(self, vector: list[float], k: int = 4) -> list[ElementoBusqueda]:
        """Devuelve una 'ficha' por entidad semilla: la entidad y sus relaciones directas.

        Las fichas tienen la misma forma que un chunk (ElementoBusqueda), asi compiten
        con los chunks del vector DB en el reranking y el LLM las recibe igual.
        """
        ...
