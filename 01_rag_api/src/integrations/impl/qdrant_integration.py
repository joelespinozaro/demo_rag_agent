from langchain_openai import OpenAIEmbeddings
from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient

from src.dto.busqueda_dto import ElementoBusqueda
from src.integrations.db_vectorial_integration import DbVectorialIntegration
from src.utils.environment import OPENAI_API_KEY, OPENAI_EMBEDDING_MODEL, QDRANT_API_KEY, QDRANT_COLLECTION_NAME, QDRANT_URL


class QdrantIntegration(DbVectorialIntegration):
    def __init__(self):
        client = QdrantClient(
            url=QDRANT_URL,
            api_key=QDRANT_API_KEY,
            timeout=60,
        )

        embeddings = OpenAIEmbeddings(api_key=OPENAI_API_KEY, model=OPENAI_EMBEDDING_MODEL)

        self._vector_store = QdrantVectorStore(
            client=client,
            collection_name=QDRANT_COLLECTION_NAME,
            embedding=embeddings,
        )

    def search(self, vector: list[float], limit: int = 5) -> list[ElementoBusqueda]:
        docs_with_scores = self._vector_store.similarity_search_with_score_by_vector(vector, k=limit)
        return [
            ElementoBusqueda(
                id=str(doc.metadata.get('_id', '')),
                source_file=doc.metadata.get('source_file', ''),
                document_name=doc.metadata.get('document_name', ''),
                content=doc.page_content,
                score=score,
            )
            for doc, score in docs_with_scores
        ]
