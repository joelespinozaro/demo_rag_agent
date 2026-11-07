"""Compara el top-5 de busqueda densa, BM25 e hibrida para una misma pregunta.

Uso (desde 01_rag_api):
    python -m scripts.compare_search "¿Que docente es experto en TOGAF?"
"""

import sys

from langchain_openai import OpenAIEmbeddings

from src.integrations.impl.qdrant_hybrid_integration import QdrantHybridIntegration
from src.utils.environment import OPENAI_API_KEY, OPENAI_EMBEDDING_MODEL


def show(title: str, results) -> None:
    print(f"\n=== {title} ===")
    for pos, r in enumerate(results, start=1):
        snippet = r.content.replace("\n", " ")[:95]
        print(f"{pos}. [{r.source_file}] {r.score:.3f}  {snippet}")


def main() -> None:
    question = " ".join(sys.argv[1:]) or "¿Que docente es experto en TOGAF?"
    print(f"Pregunta: {question}")
    vector = OpenAIEmbeddings(api_key=OPENAI_API_KEY, model=OPENAI_EMBEDDING_MODEL).embed_query(question)
    search = QdrantHybridIntegration()
    show("Densa (significado)", search.search_single(vector, None))
    show("BM25 (palabras exactas)", search.search_single(None, question))
    show("Hibrida (RRF)", search.search(vector, limit=5, query_text=question))


if __name__ == "__main__":
    main()
