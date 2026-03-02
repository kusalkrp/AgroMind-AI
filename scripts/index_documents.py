"""
Phase 2 — Full document indexing into Qdrant.

Processes all PDFs in data/raw/, extracts text, chunks, embeds, and upserts
into the 'agromind' Qdrant collection. Skips documents already indexed
(deduplication by source path).

Usage (inside worker container):
    python scripts/index_documents.py [--strategy fixed] [--force]
"""
from __future__ import annotations

import argparse
import glob
import sys
import time
from pathlib import Path

sys.path.insert(0, "/app")

from loguru import logger

from ingestion.processors.pdf_extractor import extract_pdf
from ingestion.processors.metadata_tagger import MetadataTagger
from ingestion.chunkers.fixed_chunker import chunk as fixed_chunk
from ingestion.chunkers.sliding_chunker import chunk as sliding_chunk
from knowledge.retrievers.semantic_retriever import (
    ensure_collection,
    get_client,
    upsert_chunks,
)

COLLECTION = "agromind"

STRATEGY_MAP = {
    "fixed": fixed_chunk,
    "sliding": sliding_chunk,
}


def already_indexed(client, source_path: str) -> int:
    """Return number of points already in Qdrant for this source path."""
    from qdrant_client.models import FieldCondition, Filter, MatchValue

    result = client.count(
        collection_name=COLLECTION,
        count_filter=Filter(
            must=[FieldCondition(key="source", match=MatchValue(value=source_path))]
        ),
        exact=True,
    )
    return result.count


def index_pdf(
    pdf_path: str,
    tagger: MetadataTagger,
    chunk_fn,
    client,
    force: bool = False,
) -> int:
    """Extract, tag, chunk, and upsert a single PDF. Returns points upserted."""
    existing = already_indexed(client, pdf_path)
    if existing > 0 and not force:
        logger.info(f"Skipping (already indexed {existing} pts): {Path(pdf_path).name}")
        return 0

    logger.info(f"Processing: {Path(pdf_path).name}")
    t0 = time.time()

    # Extract text
    try:
        doc = extract_pdf(pdf_path)
    except Exception as exc:
        logger.error(f"  Extract failed: {exc}")
        return 0

    if not doc.success or not doc.full_text.strip():
        logger.warning(f"  Empty text after extraction — skipping")
        return 0

    full_text = doc.full_text

    # Tag metadata
    try:
        meta = tagger.tag(full_text)
        meta_dict = meta.model_dump()
    except Exception as exc:
        logger.warning(f"  Tagging failed ({exc}) — using empty metadata")
        meta_dict = {}

    # Chunk
    try:
        nodes = chunk_fn(full_text)
    except Exception as exc:
        logger.error(f"  Chunking failed: {exc}")
        return 0

    if not nodes:
        logger.warning(f"  No chunks produced — skipping")
        return 0

    # Build chunk dicts
    chunks = [
        {"text": node.text, "metadata": {**meta_dict, "page_count": doc.total_pages}}
        for node in nodes
        if node.text.strip()
    ]

    # Upsert
    try:
        n = upsert_chunks(chunks, source_path=pdf_path)
    except Exception as exc:
        logger.error(f"  Upsert failed: {exc}")
        return 0

    elapsed = time.time() - t0
    logger.success(f"  {n} chunks indexed in {elapsed:.1f}s  [{Path(pdf_path).name}]")
    return n


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--strategy", default="fixed", choices=list(STRATEGY_MAP))
    parser.add_argument("--force", action="store_true", help="Re-index even if already present")
    args = parser.parse_args()

    chunk_fn = STRATEGY_MAP[args.strategy]
    logger.info(f"Chunking strategy: {args.strategy}")

    # Ensure collection exists with correct dims
    ensure_collection()

    client = get_client()
    tagger = MetadataTagger()

    pdfs = sorted(glob.glob("/app/data/raw/**/*.pdf", recursive=True))
    logger.info(f"Found {len(pdfs)} PDFs to process")

    total_indexed = 0
    skipped = 0
    failed = 0

    for i, pdf_path in enumerate(pdfs, 1):
        logger.info(f"[{i}/{len(pdfs)}] {Path(pdf_path).name}")
        n = index_pdf(pdf_path, tagger, chunk_fn, client, force=args.force)
        if n == 0:
            existing = already_indexed(client, pdf_path)
            if existing > 0:
                skipped += 1
            else:
                failed += 1
        else:
            total_indexed += n

    # Final stats
    collection_info = client.get_collection(COLLECTION)
    total_points = collection_info.points_count

    logger.info("=" * 60)
    logger.info(f"Indexing complete.")
    logger.info(f"  New chunks indexed : {total_indexed}")
    logger.info(f"  PDFs skipped       : {skipped}")
    logger.info(f"  PDFs failed        : {failed}")
    logger.info(f"  Total Qdrant pts   : {total_points}")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
