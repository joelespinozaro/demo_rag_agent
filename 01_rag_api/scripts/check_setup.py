"""Revisa que tu .env y tus bases de datos esten listos antes del laboratorio.

Uso (desde 01_rag_api):
    python -m scripts.check_setup
"""

from qdrant_client import QdrantClient
from sqlalchemy import create_engine, inspect

from src.utils.environment import (
    DATABASE_URL,
    GRAPH_ENABLED,
    NEO4J_URI,
    OPENAI_API_KEY,
    QDRANT_API_KEY,
    QDRANT_COLLECTION_NAME,
    QDRANT_HYBRID_COLLECTION,
    QDRANT_URL,
)

OK, FALTA = "OK   ", "FALTA"


def check_openai() -> None:
    estado = OK if OPENAI_API_KEY.startswith("sk-") else FALTA
    print(f"[{estado}] OpenAI: OPENAI_API_KEY {'parece valida' if estado == OK else 'no empieza con sk-'}")


def check_qdrant() -> None:
    try:
        client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
        nombres = {c.name for c in client.get_collections().collections}
    except Exception as exc:  # noqa: BLE001
        print(f"[{FALTA}] Qdrant: no se pudo conectar a {QDRANT_URL} ({type(exc).__name__})")
        return
    for nombre, cuando in [(QDRANT_COLLECTION_NAME, "sesion anterior: setup/qdrant-db.ipynb"),
                           (QDRANT_HYBRID_COLLECTION, "Lab 1: python -m scripts.build_hybrid_index")]:
        if nombre in nombres:
            print(f"[{OK}] Qdrant: coleccion '{nombre}' con {client.count(nombre).count} puntos")
        else:
            print(f"[{FALTA}] Qdrant: no existe la coleccion '{nombre}' ({cuando})")


def check_postgres() -> None:
    url = DATABASE_URL.replace("postgresql://", "postgresql+psycopg2://", 1) if DATABASE_URL.startswith("postgresql://") else DATABASE_URL
    try:
        engine = create_engine(url)
        tablas = inspect(engine).get_table_names()
    except Exception as exc:  # noqa: BLE001
        print(f"[{FALTA}] PostgreSQL: no se pudo conectar ({type(exc).__name__}). Revisa DATABASE_URL")
        return
    if "history" in tablas:
        print(f"[{OK}] PostgreSQL: tabla 'history' lista")
    else:
        print(f"[{FALTA}] PostgreSQL: no existe la tabla 'history' (ejecuta setup/database.sql en el SQL Editor de Neon)")


def check_neo4j() -> None:
    if not GRAPH_ENABLED:
        print("[-    ] Neo4j: GRAPH_ENABLED=false. Se configura en el Lab 2 (python -m scripts.check_neo4j)")
    elif not NEO4J_URI:
        print(f"[{FALTA}] Neo4j: GRAPH_ENABLED=true pero falta NEO4J_URI")
    else:
        print("[-    ] Neo4j: configurado. Verificalo con python -m scripts.check_neo4j")


if __name__ == "__main__":
    check_openai()
    check_qdrant()
    check_postgres()
    check_neo4j()
