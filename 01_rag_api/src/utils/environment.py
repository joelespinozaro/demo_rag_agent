from decouple import config

OPENAI_API_KEY: str = config("OPENAI_API_KEY")
OPENAI_MODEL: str = config("OPENAI_MODEL")
OPENAI_EMBEDDING_MODEL: str = config("OPENAI_EMBEDDING_MODEL", default="text-embedding-3-small")

ASSISTANT_NAME: str = config("ASSISTANT_NAME", default="Asistente")

DATABASE_URL: str = config("DATABASE_URL")
HISTORY_LIMIT: int = config("HISTORY_LIMIT", default=10, cast=int)
RETRIEVAL_LIMIT: int = config("RETRIEVAL_LIMIT", default=5, cast=int)
QUERY_EXPANSION_COUNT: int = config("QUERY_EXPANSION_COUNT", default=3, cast=int)
RETRIEVAL_CANDIDATES: int = config("RETRIEVAL_CANDIDATES", default=15, cast=int)

QDRANT_URL: str | None = config("QDRANT_URL", default=None)
QDRANT_API_KEY: str | None = config("QDRANT_API_KEY", default=None)
QDRANT_COLLECTION_NAME: str = config("QDRANT_COLLECTION_NAME", default="documents")
QDRANT_HYBRID_COLLECTION: str = config("QDRANT_HYBRID_COLLECTION", default=f"{QDRANT_COLLECTION_NAME}-hybrid")
# dense = solo vectores (coleccion original) | hybrid = vectores + BM25 con RRF
SEARCH_MODE: str = config("SEARCH_MODE", default="hybrid")
HYBRID_PREFETCH_LIMIT: int = config("HYBRID_PREFETCH_LIMIT", default=30, cast=int)
HYBRID_RRF_K: int = config("HYBRID_RRF_K", default=60, cast=int)

NEON_API_KEY: str | None = config("NEON_API_KEY", default=None)

# GraphRAG con Neo4j (rama rag_agents_graphrag)
GRAPH_ENABLED: bool = config("GRAPH_ENABLED", default=True, cast=bool)
NEO4J_URI: str | None = config("NEO4J_URI", default=None)
NEO4J_USERNAME: str = config("NEO4J_USERNAME", default="neo4j")
NEO4J_PASSWORD: str | None = config("NEO4J_PASSWORD", default=None)
NEO4J_DATABASE: str = config("NEO4J_DATABASE", default="neo4j")
GRAPH_SEED_K: int = config("GRAPH_SEED_K", default=4, cast=int)
GRAPH_MAX_RELATIONS: int = config("GRAPH_MAX_RELATIONS", default=15, cast=int)

LANGSMITH_API_KEY: str | None = config("LANGSMITH_API_KEY", default=None)
LANGSMITH_PROJECT: str = config("LANGSMITH_PROJECT", default="agente-mcp")
LANGSMITH_ENDPOINT: str = config("LANGSMITH_ENDPOINT", default="https://api.smith.langchain.com")

