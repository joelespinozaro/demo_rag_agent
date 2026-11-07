"""Crea la coleccion hibrida en Qdrant: un vector denso y uno disperso por chunk.

Uso (desde la carpeta 01_rag_api, con el .env configurado):
    python -m scripts.build_hybrid_index

La coleccion se llama <QDRANT_COLLECTION_NAME>-hybrid y no toca la coleccion
original, asi puedes comparar ambas.
"""

import uuid

from langchain_openai import OpenAIEmbeddings
from qdrant_client import QdrantClient, models

from scripts.chunking import load_chunks
from src.integrations.impl.bm25_encoder import encode_document, tokenize
from src.utils.environment import (
    OPENAI_API_KEY,
    OPENAI_EMBEDDING_MODEL,
    QDRANT_API_KEY,
    QDRANT_HYBRID_COLLECTION,
    QDRANT_URL,
)

DENSE = "dense"
SPARSE = "bm25"
BATCH = 64


def main() -> None:
    chunks = load_chunks()
    print(f"[1/4] {len(chunks)} chunks cargados desde setup/data")

    embedder = OpenAIEmbeddings(api_key=OPENAI_API_KEY, model=OPENAI_EMBEDDING_MODEL)
    texts = [c["content"] for c in chunks]
    dense_vectors: list[list[float]] = []
    for start in range(0, len(texts), BATCH):
        dense_vectors.extend(embedder.embed_documents(texts[start:start + BATCH]))
    dim = len(dense_vectors[0])
    print(f"[2/4] Embeddings densos listos ({dim} dimensiones)")

    avg_len = sum(len(tokenize(t)) for t in texts) / len(texts)
    sparse_vectors = [encode_document(t, avg_len) for t in texts]
    print(f"[3/4] Vectores BM25 listos (longitud promedio: {avg_len:.0f} terminos)")

    client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY, timeout=60)
    if client.collection_exists(QDRANT_HYBRID_COLLECTION):
        client.delete_collection(QDRANT_HYBRID_COLLECTION)
    client.create_collection(
        collection_name=QDRANT_HYBRID_COLLECTION,
        vectors_config={DENSE: models.VectorParams(size=dim, distance=models.Distance.COSINE)},
        sparse_vectors_config={SPARSE: models.SparseVectorParams(modifier=models.Modifier.IDF)},
    )

    points = []
    for chunk, dense, (idx, val) in zip(chunks, dense_vectors, sparse_vectors):
        points.append(
            models.PointStruct(
                id=str(uuid.uuid5(uuid.NAMESPACE_URL, chunk["chunk_id"])),
                vector={DENSE: dense, SPARSE: models.SparseVector(indices=idx, values=val)},
                payload={
                    "chunk_id": chunk["chunk_id"],
                    "page_content": chunk["content"],
                    "metadata": chunk["metadata"],
                },
            )
        )
    client.upsert(collection_name=QDRANT_HYBRID_COLLECTION, points=points)
    print(f"[4/4] {len(points)} puntos en la coleccion '{QDRANT_HYBRID_COLLECTION}'")


if __name__ == "__main__":
    main()
