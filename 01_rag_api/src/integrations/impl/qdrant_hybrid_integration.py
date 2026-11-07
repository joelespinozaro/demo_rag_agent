from qdrant_client import QdrantClient, models

from src.dto.busqueda_dto import ElementoBusqueda
from src.integrations.db_vectorial_integration import DbVectorialIntegration
from src.integrations.impl.bm25_encoder import encode_query
from src.utils.environment import (
    HYBRID_PREFETCH_LIMIT,
    HYBRID_RRF_K,
    QDRANT_API_KEY,
    QDRANT_HYBRID_COLLECTION,
    QDRANT_URL,
)


class QdrantHybridIntegration(DbVectorialIntegration):
    """Busqueda hibrida: semantica (vector denso) + lexica (BM25) fusionadas con RRF.

    Qdrant ejecuta las dos busquedas en paralelo (prefetch) y fusiona los dos
    rankings por posicion con Reciprocal Rank Fusion, todo en una sola llamada.
    """

    def __init__(self, client: QdrantClient | None = None, collection: str = QDRANT_HYBRID_COLLECTION):
        self._client = client or QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY, timeout=60)
        self._collection = collection

    def search(self, vector: list[float], limit: int = 5, query_text: str | None = None) -> list[ElementoBusqueda]:
        prefetch = [models.Prefetch(query=vector, using="dense", limit=HYBRID_PREFETCH_LIMIT)]
        if query_text:
            indices, values = encode_query(query_text)
            if indices:
                prefetch.append(
                    models.Prefetch(
                        query=models.SparseVector(indices=indices, values=values),
                        using="bm25",
                        limit=HYBRID_PREFETCH_LIMIT,
                    )
                )

        try:
            # RRF con k configurable (k=60 es el valor del paper original).
            fusion = models.RrfQuery(rrf=models.Rrf(k=HYBRID_RRF_K))
            response = self._client.query_points(
                collection_name=self._collection, prefetch=prefetch, query=fusion, limit=limit, with_payload=True
            )
        except Exception:
            # Servidores Qdrant antiguos no aceptan k: usan el RRF por defecto.
            response = self._client.query_points(
                collection_name=self._collection,
                prefetch=prefetch,
                query=models.FusionQuery(fusion=models.Fusion.RRF),
                limit=limit,
                with_payload=True,
            )
        return [_to_elemento(point) for point in response.points]

    def search_single(self, vector: list[float] | None, query_text: str | None, limit: int = 5) -> list[ElementoBusqueda]:
        """Solo un buscador (denso o BM25). Lo usa scripts/compare_search.py para comparar."""
        if vector is not None:
            response = self._client.query_points(
                collection_name=self._collection, query=vector, using="dense", limit=limit, with_payload=True
            )
        else:
            indices, values = encode_query(query_text or "")
            response = self._client.query_points(
                collection_name=self._collection,
                query=models.SparseVector(indices=indices, values=values),
                using="bm25",
                limit=limit,
                with_payload=True,
            )
        return [_to_elemento(point) for point in response.points]


def _to_elemento(point: models.ScoredPoint) -> ElementoBusqueda:
    payload = point.payload or {}
    metadata = payload.get("metadata", {})
    return ElementoBusqueda(
        id=str(point.id),
        source_file=metadata.get("source_file", ""),
        document_name=metadata.get("document_name", ""),
        content=payload.get("page_content", ""),
        score=float(point.score),
    )
