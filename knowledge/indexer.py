"""
Indexer — bridges the ingestion pipeline and the Qdrant vector store.

Takes chunked nodes from ingestion/chunkers/ and:
  1. Embeds text with Gemini (dense vector)
  2. Computes BM25-style sparse vector
  3. Upserts both to Qdrant with full metadata payload

Called by the `chunk_and_embed` Celery task in ingestion/pipeline.py.
"""
from __future__ import annotations

from pathlib import Path
from typing import Literal

from loguru import logger

from knowledge.retrievers.semantic_retriever import ensure_collection, upsert_chunks

ChunkStrategy = Literal["fixed", "sliding", "semantic", "parent_child", "late"]


def index_document(
    text: str,
    metadata: dict,
    strategy: ChunkStrategy = "fixed",
    source_path: str = "",
) -> int:
    """
    Chunk text, embed, and upsert to Qdrant.

    Args:
        text: Raw document text.
        metadata: DocumentMetadata dict to attach to every chunk.
        strategy: Chunking strategy name.
        source_path: Source file path for provenance tracking.

    Returns:
        Number of chunks indexed.
    """
    from ingestion.chunkers import (
        fixed_chunker,
        late_chunker,
        parent_child_chunker,
        semantic_chunker,
        sliding_chunker,
    )

    chunker_map = {
        "fixed": fixed_chunker,
        "sliding": sliding_chunker,
        "semantic": semantic_chunker,
        "parent_child": parent_child_chunker,
        "late": late_chunker,
    }

    if strategy not in chunker_map:
        raise ValueError(f"Unknown chunking strategy: {strategy!r}")

    ensure_collection()

    chunker = chunker_map[strategy]
    nodes = chunker.chunk(text, metadata)

    if not nodes:
        logger.warning(f"index_document: no chunks produced for {source_path!r}")
        return 0

    # For parent_child, only index leaf nodes (smallest chunks) to avoid
    # embedding redundant parent context at retrieval time.
    if strategy == "parent_child":
        from ingestion.chunkers.parent_child_chunker import get_leaf_chunks
        nodes = get_leaf_chunks(text, metadata)

    chunks = [
        {"text": node.get_content(), "metadata": node.metadata}
        for node in nodes
        if node.get_content().strip()
    ]

    indexed = upsert_chunks(chunks, source_path=source_path)
    logger.info(
        f"index_document: {indexed}/{len(chunks)} chunks indexed "
        f"(strategy={strategy}, source={source_path!r})"
    )
    return indexed


def index_pdf(
    filepath: Path | str,
    strategy: ChunkStrategy = "fixed",
) -> int:
    """
    Full pipeline: extract PDF → tag metadata → chunk → index.

    Convenience wrapper for CLI/script use outside Celery.
    """
    from ingestion.processors.pdf_extractor import extract_pdf
    from ingestion.processors.metadata_tagger import MetadataTagger

    filepath = Path(filepath)
    logger.info(f"index_pdf: {filepath.name} (strategy={strategy})")

    doc = extract_pdf(filepath)
    if not doc.success:
        logger.error(f"index_pdf: extraction failed — {doc.error}")
        return 0

    tagger = MetadataTagger()
    metadata = tagger.tag(doc.full_text[:4000])

    return index_document(
        text=doc.full_text,
        metadata=metadata.model_dump(),
        strategy=strategy,
        source_path=str(filepath),
    )
