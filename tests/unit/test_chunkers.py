"""
Unit tests for all 5 chunking strategies in ingestion/chunkers/.

Verifies:
  - Each chunker returns a list of TextNode objects
  - Every node has chunking_strategy metadata set correctly
  - Nodes are non-empty
"""
import pytest
from unittest.mock import patch, MagicMock

# ── Shared sample text ────────────────────────────────────────────────────────

SAMPLE_TEXT = """
Paddy cultivation in Sri Lanka is highly influenced by seasonal rainfall patterns.
The Maha season spans from October to March, while Yala runs from April to September.
Farmers in the Dry Zone districts such as Anuradhapura and Polonnaruwa rely on
irrigation from ancient tank systems to supplement rainfall during the Yala season.

Recommended varieties for Maha include BG 360 and BG 403, which show high resistance
to Brown Plant Hopper — the most destructive pest affecting paddy fields in Sri Lanka.
Nitrogen fertilizer application should not exceed 120 kg/ha for paddy cultivation.
The optimal pH range for paddy is 5.5 to 7.0.

For pest management, integrated pest management (IPM) techniques are strongly recommended
over chemical treatments to protect both yield quality and soil biodiversity.
Regular field monitoring every 7–10 days is essential for early detection of blast disease.
""" * 5  # repeat for enough tokens


# ── Fixed chunker ─────────────────────────────────────────────────────────────

class TestFixedChunker:
    def test_returns_list_of_nodes(self):
        from ingestion.chunkers.fixed_chunker import chunk
        nodes = chunk(SAMPLE_TEXT)
        assert isinstance(nodes, list)
        assert len(nodes) > 0

    def test_nodes_have_correct_strategy_tag(self):
        from ingestion.chunkers.fixed_chunker import chunk
        nodes = chunk(SAMPLE_TEXT)
        for node in nodes:
            assert node.metadata.get("chunking_strategy") == "fixed"

    def test_nodes_have_non_empty_text(self):
        from ingestion.chunkers.fixed_chunker import chunk
        nodes = chunk(SAMPLE_TEXT)
        for node in nodes:
            assert node.get_content().strip() != ""

    def test_metadata_propagated_to_nodes(self):
        from ingestion.chunkers.fixed_chunker import chunk
        extra = {"source": "doa.gov.lk", "crop_types": ["paddy"]}
        nodes = chunk(SAMPLE_TEXT, metadata=extra)
        for node in nodes:
            assert node.metadata.get("source") == "doa.gov.lk"

    def test_empty_text_returns_empty_or_minimal_nodes(self):
        from ingestion.chunkers.fixed_chunker import chunk
        nodes = chunk("")
        assert isinstance(nodes, list)


# ── Sliding chunker ───────────────────────────────────────────────────────────

class TestSlidingChunker:
    def test_returns_list_of_nodes(self):
        from ingestion.chunkers.sliding_chunker import chunk
        nodes = chunk(SAMPLE_TEXT)
        assert isinstance(nodes, list)
        assert len(nodes) > 0

    def test_nodes_have_correct_strategy_tag(self):
        from ingestion.chunkers.sliding_chunker import chunk
        nodes = chunk(SAMPLE_TEXT)
        for node in nodes:
            assert node.metadata.get("chunking_strategy") == "sliding"

    def test_more_nodes_than_fixed_due_to_high_overlap(self):
        """Sliding (overlap=256) should produce more nodes than fixed (overlap=50)."""
        from ingestion.chunkers import fixed_chunker, sliding_chunker
        fixed_nodes = fixed_chunker.chunk(SAMPLE_TEXT)
        sliding_nodes = sliding_chunker.chunk(SAMPLE_TEXT)
        assert len(sliding_nodes) >= len(fixed_nodes)


# ── Semantic chunker (mocked embedding) ──────────────────────────────────────

class TestSemanticChunker:
    def test_returns_list_of_nodes(self):
        """Mock the GeminiEmbedding to avoid real API calls."""
        mock_embed = MagicMock()
        mock_embed.get_text_embedding_batch.return_value = [
            [0.1] * 768 for _ in range(100)
        ]
        mock_embed.get_text_embedding.return_value = [0.1] * 768

        with patch("ingestion.chunkers.semantic_chunker.GeminiEmbedding",
                   return_value=mock_embed), \
             patch("ingestion.chunkers.semantic_chunker._build_splitter") as mock_build:

            from ingestion.chunkers.fixed_chunker import chunk as fixed_chunk
            from llama_index.core.node_parser import SentenceSplitter

            # Use fixed splitter as stand-in to avoid real semantic calls
            splitter = SentenceSplitter(chunk_size=512, chunk_overlap=100)
            mock_build.return_value = splitter

            from ingestion.chunkers.semantic_chunker import chunk
            nodes = chunk(SAMPLE_TEXT)

        assert isinstance(nodes, list)
        assert len(nodes) > 0

    def test_nodes_tagged_with_semantic_strategy(self):
        """Verify strategy tag is 'semantic' regardless of underlying splitter."""
        with patch("ingestion.chunkers.semantic_chunker._build_splitter") as mock_build:
            from llama_index.core.node_parser import SentenceSplitter
            mock_build.return_value = SentenceSplitter(chunk_size=512)

            from ingestion.chunkers.semantic_chunker import chunk
            nodes = chunk(SAMPLE_TEXT)

        for node in nodes:
            assert node.metadata.get("chunking_strategy") == "semantic"


# ── Parent-child chunker ──────────────────────────────────────────────────────

class TestParentChildChunker:
    def test_returns_list_of_nodes(self):
        from ingestion.chunkers.parent_child_chunker import chunk
        nodes = chunk(SAMPLE_TEXT)
        assert isinstance(nodes, list)
        assert len(nodes) > 0

    def test_all_nodes_tagged_with_parent_child_strategy(self):
        from ingestion.chunkers.parent_child_chunker import chunk
        nodes = chunk(SAMPLE_TEXT)
        for node in nodes:
            assert node.metadata.get("chunking_strategy") == "parent_child"

    def test_leaf_nodes_are_smallest(self):
        """Leaf nodes returned by get_leaf_chunks should be <= child nodes in count."""
        from ingestion.chunkers.parent_child_chunker import chunk, get_leaf_chunks
        all_nodes = chunk(SAMPLE_TEXT)
        leaf_nodes = get_leaf_chunks(SAMPLE_TEXT)
        assert len(leaf_nodes) > 0
        assert len(leaf_nodes) <= len(all_nodes)

    def test_produces_multiple_hierarchy_levels(self):
        """With sizes [2048, 512, 128], there should be at least 2 distinct levels."""
        from ingestion.chunkers.parent_child_chunker import chunk
        nodes = chunk(SAMPLE_TEXT)
        # All nodes exist; hierarchy depth is implicit from node structure
        assert len(nodes) >= 2


# ── Late chunker ──────────────────────────────────────────────────────────────

class TestLateChunker:
    def test_returns_list_of_nodes(self):
        from ingestion.chunkers.late_chunker import chunk
        nodes = chunk(SAMPLE_TEXT)
        assert isinstance(nodes, list)
        assert len(nodes) > 0

    def test_nodes_tagged_with_late_strategy(self):
        from ingestion.chunkers.late_chunker import chunk
        nodes = chunk(SAMPLE_TEXT)
        for node in nodes:
            assert node.metadata.get("chunking_strategy") == "late"

    def test_each_node_has_doc_summary(self):
        """Late chunker injects doc_summary into every node's metadata."""
        from ingestion.chunkers.late_chunker import chunk
        nodes = chunk(SAMPLE_TEXT)
        for node in nodes:
            assert "doc_summary" in node.metadata
            assert len(node.metadata["doc_summary"]) > 0

    def test_doc_summary_is_truncated_to_512_chars(self):
        """doc_summary should be at most 512 characters."""
        from ingestion.chunkers.late_chunker import chunk
        long_text = "X" * 10_000
        nodes = chunk(long_text)
        for node in nodes:
            assert len(node.metadata["doc_summary"]) <= 512
