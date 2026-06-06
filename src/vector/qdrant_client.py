# src/vector/qdrant_client.py
"""Thin wrapper around Qdrant client for Shadow‑Ops memory layer.
The client is instantiated once per process and reused.
"""

import os
from typing import List, Tuple

from qdrant_client import QdrantClient
from qdrant_client.http import models as rest

# Qdrant connection configuration – read from environment or defaults
_QDRANT_HOST = os.getenv("QDRANT_HOST", "qdrant")
_QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))
_QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")  # optional

# Initialise a singleton client (process‑wide)
_client = QdrantClient(
    host=_QDRANT_HOST,
    port=_QDRANT_PORT,
    api_key=_QDRANT_API_KEY,
    prefer_grpc=False,
)

COLLECTION_NAME = "incident_vectors"

def ensure_collection(dim: int = 768) -> None:
    """Create the collection if it does not exist.
    We use `cosine` distance for semantic similarity.
    """
    if not _client.collection_exists(COLLECTION_NAME):
        _client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=rest.VectorParams(size=dim, distance=rest.Distance.COSINE),
        )

def upsert_vectors(
    ids: List[int],
    vectors: List[List[float]],
    payloads: List[dict] | None = None,
) -> None:
    """Insert or update a batch of vectors.
    - `ids` must be unique per incident (use incident UUID hash).
    - `vectors` is a list of embedding vectors.
    - `payloads` optional metadata stored with each point.
    """
    ensure_collection(dim=len(vectors[0]))
    _client.upsert(
        collection_name=COLLECTION_NAME,
        points=[rest.PointStruct(id=id_, vector=vec, payload=payload or {}) for id_, vec in zip(ids, vectors)],
    )

def search_similar(
    query_vector: List[float], limit: int = 5, score_threshold: float = 0.6
) -> List[Tuple[int, float, dict]]:
    """Return the `limit` most similar points.
    Returns list of ``(point_id, score, payload)``.
    """
    ensure_collection(dim=len(query_vector))
    result = _client.search(
        collection_name=COLLECTION_NAME,
        query_vector=query_vector,
        limit=limit,
        score_threshold=score_threshold,
    )
    return [(hit.id, hit.score, hit.payload) for hit in result]

# Helper to delete a point (e.g., when an incident is purged)
def delete_point(point_id: int) -> None:
    if _client.collection_exists(COLLECTION_NAME):
        _client.delete(collection_name=COLLECTION_NAME, points=[point_id])
