from langchain_openai import OpenAIEmbeddings

from src.integrations.embedding_integration import EmbeddingIntegration
from src.utils.environment import OPENAI_API_KEY, OPENAI_EMBEDDING_MODEL


class OpenAIEmbeddingIntegration(EmbeddingIntegration):
    def __init__(self):
        self._embeddings = OpenAIEmbeddings(api_key=OPENAI_API_KEY, model=OPENAI_EMBEDDING_MODEL)

    def generate_embedding(self, text: str) -> list[float]:
        return self._embeddings.embed_query(text)
