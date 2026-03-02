"""
Semantic Retriever — Qdrant hybrid search.

Strategy:
  1. Dense vector (Gemini text-embedding-004, 768-d, cosine)
  2. Sparse vector (BM25-style TF-IDF via hash trick)
  3. RRF (Reciprocal Rank Fusion) to merge both ranked lists
  4. Metadata filters (crop_types, districts, document_type, season)

Returns List[str] of chunk texts — agents never touch Qdrant directly.
"""
from __future__ import annotations

import re
from collections import Counter

from loguru import logger
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    Fusion,
    FusionQuery,
    MatchAny,
    MatchValue,
    PointStruct,
    Prefetch,
    SparseIndexParams,
    SparseVector,
    SparseVectorParams,
    VectorParams,
)

from config.settings import settings
from knowledge.embedder import embed_query, embed_text

COLLECTION_NAME = settings.qdrant_collection
DENSE_DIM = settings.embedding_dim  # 3072 for gemini-embedding-001
SPARSE_INDEX_SIZE = 30_000  # hash-trick vocabulary size

_client: QdrantClient | None = None

_STOP_WORDS = frozenset(
    "the a an and or but in on at to for of with is are was were be been "
    "have has had do does did not no this that it its i we you he she they "
    "my our your his her their what which who how when where why".split()
)


# ── Client singleton ──────────────────────────────────────────────────────────

def get_client() -> QdrantClient:
    global _client
    if _client is None:
        _client = QdrantClient(
            host=settings.qdrant_host,
            port=settings.qdrant_port,
            check_compatibility=False,
        )
    return _client


# ── Collection management ─────────────────────────────────────────────────────

def ensure_collection() -> None:
    """Create the Qdrant collection if it does not already exist."""
    client = get_client()
    existing = [c.name for c in client.get_collections().collections]
    if COLLECTION_NAME in existing:
        logger.debug(f"Collection '{COLLECTION_NAME}' already exists")
        return

    client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config={
            "dense": VectorParams(size=DENSE_DIM, distance=Distance.COSINE)
        },
        sparse_vectors_config={
            "sparse": SparseVectorParams(
                index=SparseIndexParams(on_disk=False)
            )
        },
    )
    logger.info(f"Created Qdrant collection '{COLLECTION_NAME}'")


# ── Sparse vector (BM25-style) ────────────────────────────────────────────────

def compute_sparse_vector(text: str) -> SparseVector:
    """
    Compute a BM25-style sparse vector using a hash-trick vocabulary.

    Each unique token maps to an index via hash(token) % SPARSE_INDEX_SIZE.
    Values are normalised term frequencies (TF only — IDF computed at query time
    by Qdrant's dot-product scoring against stored sparse vectors).

    Note: For production, replace with fastembed SparseTextEmbedding("Qdrant/bm25")
    which provides true BM25 scoring without needing a pre-built corpus vocabulary.
    """
    tokens = re.findall(r"\b[a-z]{2,}\b", text.lower())
    tokens = [t for t in tokens if t not in _STOP_WORDS]
    if not tokens:
        return SparseVector(indices=[0], values=[0.0])

    counts = Counter(tokens)
    total = len(tokens)

    indices: list[int] = []
    values: list[float] = []
    seen_indices: set[int] = set()

    for token, count in counts.items():
        idx = hash(token) % SPARSE_INDEX_SIZE
        if idx < 0:
            idx += SPARSE_INDEX_SIZE
        if idx in seen_indices:
            # hash collision — skip duplicate index
            continue
        seen_indices.add(idx)
        indices.append(idx)
        values.append(round(count / total, 6))

    return SparseVector(indices=indices, values=values)


# ── Filters ───────────────────────────────────────────────────────────────────

def build_filter(filters: dict | None) -> Filter | None:
    """Convert a plain dict of filter criteria into a Qdrant Filter."""
    if not filters:
        return None

    conditions = []

    crop_types = filters.get("crop_types") or []
    if crop_types:
        conditions.append(
            FieldCondition(key="crop_types", match=MatchAny(any=crop_types))
        )

    district = filters.get("district")
    if district:
        conditions.append(
            FieldCondition(key="districts", match=MatchAny(any=[district]))
        )

    doc_type = filters.get("document_type")
    if doc_type:
        conditions.append(
            FieldCondition(key="document_type", match=MatchValue(value=doc_type))
        )

    season = filters.get("season")
    if season:
        conditions.append(
            FieldCondition(key="season_relevance", match=MatchAny(any=[season]))
        )

    return Filter(must=conditions) if conditions else None


# ── Hybrid search ─────────────────────────────────────────────────────────────

def hybrid_search(
    query: str,
    filters: dict | None = None,
    top_k: int = 10,
) -> list[str]:
    """
    Run hybrid (dense + sparse) search with RRF fusion.

    Args:
        query: User query string.
        filters: Optional metadata filters (crop_types, district, document_type, season).
        top_k: Number of chunks to return.

    Returns:
        List[str] of chunk texts ranked by relevance.
    """
    client = get_client()
    dense_vector = embed_query(query)
    sparse_vector = compute_sparse_vector(query)
    qdrant_filter = build_filter(filters)

    prefetch = [
        Prefetch(query=dense_vector, using="dense", limit=top_k * 2),
        Prefetch(query=sparse_vector, using="sparse", limit=top_k * 2),
    ]

    try:
        results = client.query_points(
            collection_name=COLLECTION_NAME,
            prefetch=prefetch,
            query=FusionQuery(fusion=Fusion.RRF),
            limit=top_k,
            query_filter=qdrant_filter,
            with_payload=True,
        )
        texts = [p.payload.get("text", "") for p in results.points if p.payload]
        logger.debug(f"hybrid_search returned {len(texts)} chunks for query: {query[:60]!r}")
        return texts
    except Exception as exc:
        logger.error(f"hybrid_search failed: {exc}")
        return []


# ── Upsert (called by indexer) ────────────────────────────────────────────────

def upsert_chunks(
    chunks: list[dict],
    source_path: str = "",
) -> int:
    """
    Upsert text chunks into Qdrant with dense + sparse vectors.

    Args:
        chunks: List of dicts with keys: "text", "metadata", optional "id".
        source_path: Source document path for logging.

    Returns:
        Number of points upserted.
    """
    import uuid

    client = get_client()
    ensure_collection()

    texts = [c["text"] for c in chunks]
    dense_vectors = embed_text.__wrapped__ if hasattr(embed_text, "__wrapped__") else embed_text

    points: list[PointStruct] = []
    for i, chunk in enumerate(chunks):
        text = chunk["text"]
        meta = chunk.get("metadata", {})

        try:
            dense_vec = embed_text(text)
        except Exception as exc:
            logger.warning(f"Skipping chunk {i} — embed failed: {exc}")
            continue

        sparse_vec = compute_sparse_vector(text)
        point_id = str(uuid.uuid4())

        points.append(
            PointStruct(
                id=point_id,
                vector={"dense": dense_vec, "sparse": sparse_vec},
                payload={
                    "text": text,
                    "source": source_path,
                    **meta,
                },
            )
        )

    if points:
        client.upsert(collection_name=COLLECTION_NAME, points=points, wait=True)
        logger.info(f"Upserted {len(points)} chunks from {source_path!r}")

    return len(points)
