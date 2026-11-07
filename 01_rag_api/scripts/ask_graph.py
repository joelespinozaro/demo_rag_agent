"""Muestra que fichas devuelve el grafo para una pregunta (local search), sin pasar por el API.

Uso (desde 01_rag_api):
    python -m scripts.ask_graph "¿Que docentes y egresados trabajan en Yape?"
"""

import sys

from langchain_openai import OpenAIEmbeddings

from src.integrations.impl.neo4j_graph_integration import Neo4jGraphIntegration
from src.utils.environment import GRAPH_SEED_K, OPENAI_API_KEY, OPENAI_EMBEDDING_MODEL


def main() -> None:
    question = " ".join(sys.argv[1:]) or "¿Que docentes y egresados trabajan en Yape?"
    vector = OpenAIEmbeddings(api_key=OPENAI_API_KEY, model=OPENAI_EMBEDDING_MODEL).embed_query(question)
    fichas = Neo4jGraphIntegration().search(vector, k=GRAPH_SEED_K)
    print(f"Pregunta: {question}\n")
    for i, ficha in enumerate(fichas, start=1):
        print(f"--- Semilla {i} · similitud {ficha.score:.3f} · fuentes: {ficha.source_file}")
        print(ficha.content, "\n")


if __name__ == "__main__":
    main()
