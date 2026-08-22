from abc import ABC, abstractmethod

from src.dto.busqueda_dto import ElementoBusqueda


class DbVectorialIntegration(ABC):
    @abstractmethod
    def search(self, vector: list[float], limit: int = 5) -> list[ElementoBusqueda]:
        ...
