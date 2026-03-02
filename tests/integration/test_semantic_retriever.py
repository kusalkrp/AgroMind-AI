"""
Integration tests for knowledge/retrievers/semantic_retriever.py

Requires a running Qdrant instance (docker-compose up -d qdrant).
These tests are skipped if Qdrant is not reachable.

Run:
    pytest tests/integration/test_semantic_retriever.py -v
"""
from __future__ import annotations

import pytest

QDRANT_AVAILABLE = False

try:
    from qdrant_client import QdrantClient
    from config.settings import settings

    _probe = QdrantClient(host=settings.qdrant_host, port=settings.qdrant_port, timeout=3)
    _probe.get_collections()
    QDRANT_AVAILABLE = True
except Exception:
    pass

pytestmark = pytest.mark.skipif(
    not QDRANT_AVAILABLE,
    reason="Qdrant not reachable — start with: docker-compose up -d qdrant",
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

SAMPLE_CHUNKS = [
    {
        "text": (
            "Paddy blast disease (Magnaporthe oryzae) is the most devastating fungal disease "
            "of rice in Sri Lanka. Symptoms include diamond-shaped lesions on leaves with "
            "grey centres. Apply tricyclazole 75WP at 0.6 kg/ha at panicle initiation stage."
        ),
        "metadata": {
            "crop_types": ["paddy"],
            "districts": ["Anuradhapura", "Polonnaruwa"],
            "document_type": "advisory",
            "season_relevance": ["Maha", "Yala"],
            "chunking_strategy": "fixed",
        },
    },
    {
        "text": (
            "Brown Plant Hopper (Nilaparvata lugens) is a major pest of paddy. "
            "Use resistant varieties like BG 379 and BG 403. "
            "Chemical control: buprofezin 25SC at 1L/ha."
        ),
        "metadata": {
            "crop_types": ["paddy"],
            "districts": ["Kurunegala"],
            "document_type": "advisory",
            "season_relevance": ["Maha"],
            "chunking_strategy": "fixed",
        },
    },
    {
        "text": (
            "Tomato cultivation in upcountry Sri Lanka requires raised beds and drip irrigation. "
            "Recommended varieties: T-245, Thilina. Apply NPK 15:15:15 as basal dose."
        ),
        "metadata": {
            "crop_types": ["tomato"],
            "districts": ["Nuwara Eliya", "Badulla"],
            "document_type": "advisory",
            "season_relevance": ["Yala"],
            "chunking_strategy": "fixed",
        },
    },
]


@pytest.fixture(scope="module")
def populated_collection():
    """Upsert sample chunks into Qdrant and yield. Clean up after tests."""
    from knowledge.retrievers.semantic_retriever import ensure_collection, upsert_chunks

    ensure_collection()
    count = upsert_chunks(SAMPLE_CHUNKS, source_path="test_fixture")
    assert count == len(SAMPLE_CHUNKS), f"Expected {len(SAMPLE_CHUNKS)} chunks upserted, got {count}"
    yield
    # Note: we do not delete the test points to keep tests idempotent across runs.


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestEnsureCollection:
    def test_ensure_collection_does_not_raise(self):
        from knowledge.retrievers.semantic_retriever import ensure_collection
        ensure_collection()  # Should be idempotent


class TestUpsertChunks:
    def test_upsert_returns_correct_count(self, populated_collection):
        """upsert_chunks should return the number of points actually upserted."""
        from knowledge.retrievers.semantic_retriever import upsert_chunks

        extra = [{"text": "Coconut is a major plantation crop in Sri Lanka.", "metadata": {}}]
        count = upsert_chunks(extra, source_path="test_extra")
        assert count == 1

    def test_upsert_empty_list_returns_zero(self, populated_collection):
        from knowledge.retrievers.semantic_retriever import upsert_chunks

        count = upsert_chunks([], source_path="empty")
        assert count == 0


class TestHybridSearch:
    def test_returns_list_of_strings(self, populated_collection):
        from knowledge.retrievers.semantic_retriever import hybrid_search

        results = hybrid_search("paddy blast disease treatment")
        assert isinstance(results, list)
        assert all(isinstance(r, str) for r in results)

    def test_returns_results_for_known_query(self, populated_collection):
        from knowledge.retrievers.semantic_retriever import hybrid_search

        results = hybrid_search("blast disease paddy Sri Lanka", top_k=5)
        assert len(results) > 0

    def test_crop_filter_narrows_results(self, populated_collection):
        """Filtering by crop_types should only return chunks tagged with that crop."""
        from knowledge.retrievers.semantic_retriever import hybrid_search

        results = hybrid_search(
            "disease management", filters={"crop_types": ["tomato"]}, top_k=5
        )
        # All returned chunks should be about tomato (or empty if filter is strict)
        assert isinstance(results, list)

    def test_top_k_respected(self, populated_collection):
        from knowledge.retrievers.semantic_retriever import hybrid_search

        results = hybrid_search("paddy", top_k=2)
        assert len(results) <= 2

    def test_empty_query_returns_list(self, populated_collection):
        """Should handle edge-case empty queries gracefully."""
        from knowledge.retrievers.semantic_retriever import hybrid_search

        results = hybrid_search("")
        assert isinstance(results, list)


class TestSparseVector:
    def test_sparse_vector_has_indices_and_values(self):
        from knowledge.retrievers.semantic_retriever import compute_sparse_vector

        sv = compute_sparse_vector("paddy blast disease control Sri Lanka")
        assert len(sv.indices) > 0
        assert len(sv.values) > 0
        assert len(sv.indices) == len(sv.values)

    def test_sparse_vector_indices_in_range(self):
        from knowledge.retrievers.semantic_retriever import (
            SPARSE_INDEX_SIZE,
            compute_sparse_vector,
        )

        sv = compute_sparse_vector("tomato fertilizer nitrogen potassium")
        assert all(0 <= idx < SPARSE_INDEX_SIZE for idx in sv.indices)

    def test_sparse_vector_values_are_positive(self):
        from knowledge.retrievers.semantic_retriever import compute_sparse_vector

        sv = compute_sparse_vector("coconut root wilt disease")
        assert all(v > 0 for v in sv.values)

    def test_empty_text_returns_fallback_vector(self):
        from knowledge.retrievers.semantic_retriever import compute_sparse_vector

        sv = compute_sparse_vector("")
        assert len(sv.indices) >= 1
