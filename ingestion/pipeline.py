"""
Ingestion Pipeline — Celery app wired to Redis broker.

Tasks:
  crawl_doa        — crawl doa.gov.lk for PDFs
  crawl_harti      — crawl harti.gov.lk for PDFs
  scrape_market    — scrape agriculture.gov.lk weekly price tables
  extract_pdf      — extract text from a PDF file
  tag_metadata     — tag document text with Gemini
  chunk_and_embed  — chunk text into nodes (embed in Phase 2)
  ingest_weather   — fetch Open-Meteo data → TimescaleDB

Entry point:  ingest_document(filepath, strategy)
Beat schedule: weekly market + weather refresh
"""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Literal

from celery import Celery
from celery.schedules import crontab
from loguru import logger

from config.settings import settings

# ── Celery app ────────────────────────────────────────────────────────────────
app = Celery(
    "agromind_ingestion",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Asia/Colombo",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)

# ── Celery Beat schedule ──────────────────────────────────────────────────────
app.conf.beat_schedule = {
    # Weekly market price refresh — every Monday at 06:00 SL time
    "weekly-market-scrape": {
        "task": "ingestion.pipeline.scrape_market",
        "schedule": crontab(hour=6, minute=0, day_of_week="monday"),
    },
    # Weekly weather data refresh — every day at 02:00
    "daily-weather-ingest": {
        "task": "ingestion.pipeline.ingest_weather",
        "schedule": crontab(hour=2, minute=0),
    },
}

ChunkStrategy = Literal["fixed", "sliding", "semantic", "parent_child", "late"]


# ── Tasks ─────────────────────────────────────────────────────────────────────

@app.task(name="ingestion.pipeline.crawl_doa", bind=True, max_retries=3)
def crawl_doa(self, output_dir: str | None = None) -> list[str]:
    """Crawl doa.gov.lk for advisory PDFs."""
    from ingestion.crawlers.doa_crawler import crawl_doa as _crawl

    try:
        out = Path(output_dir) if output_dir else None
        paths = asyncio.run(_crawl(out))
        logger.info(f"crawl_doa: {len(paths)} PDFs downloaded")
        return [str(p) for p in paths]
    except Exception as exc:
        logger.error(f"crawl_doa failed: {exc}")
        raise self.retry(exc=exc, countdown=2 ** self.request.retries)


@app.task(name="ingestion.pipeline.crawl_harti", bind=True, max_retries=3)
def crawl_harti(self, output_dir: str | None = None) -> list[str]:
    """Crawl harti.gov.lk for research PDFs."""
    from ingestion.crawlers.harti_crawler import crawl_harti as _crawl

    try:
        out = Path(output_dir) if output_dir else None
        paths = asyncio.run(_crawl(out))
        logger.info(f"crawl_harti: {len(paths)} PDFs downloaded")
        return [str(p) for p in paths]
    except Exception as exc:
        logger.error(f"crawl_harti failed: {exc}")
        raise self.retry(exc=exc, countdown=2 ** self.request.retries)


@app.task(name="ingestion.pipeline.scrape_market", bind=True, max_retries=3)
def scrape_market(self, output_dir: str | None = None) -> list[str]:
    """Scrape weekly market price tables from agriculture.gov.lk."""
    from ingestion.crawlers.market_price_scraper import scrape_market_prices as _scrape

    try:
        out = Path(output_dir) if output_dir else None
        paths = asyncio.run(_scrape(out))
        logger.info(f"scrape_market: {len(paths)} CSV files written")
        return [str(p) for p in paths]
    except Exception as exc:
        logger.error(f"scrape_market failed: {exc}")
        raise self.retry(exc=exc, countdown=2 ** self.request.retries)


@app.task(name="ingestion.pipeline.extract_pdf", bind=True, max_retries=2)
def extract_pdf(self, filepath: str) -> dict:
    """Extract text from a PDF file. Returns serialisable dict of ExtractedDocument."""
    from ingestion.processors.pdf_extractor import extract_pdf as _extract

    try:
        result = _extract(Path(filepath))
        if not result.success:
            raise RuntimeError(result.error)
        return {
            "filepath": str(result.filepath),
            "total_pages": result.total_pages,
            "ocr_page_count": result.ocr_page_count,
            "full_text": result.full_text,
            "pages": [
                {"page_num": p.page_num, "text": p.text, "used_ocr": p.used_ocr}
                for p in result.pages
            ],
        }
    except Exception as exc:
        logger.error(f"extract_pdf failed for {filepath}: {exc}")
        raise self.retry(exc=exc, countdown=5)


@app.task(name="ingestion.pipeline.tag_metadata", bind=True, max_retries=2)
def tag_metadata(self, text: str) -> dict:
    """Tag document text with Gemini metadata extraction."""
    from ingestion.processors.metadata_tagger import MetadataTagger

    try:
        tagger = MetadataTagger()
        meta = tagger.tag(text)
        return meta.model_dump()
    except Exception as exc:
        logger.error(f"tag_metadata failed: {exc}")
        raise self.retry(exc=exc, countdown=10)


@app.task(name="ingestion.pipeline.chunk_and_embed", bind=True, max_retries=2)
def chunk_and_embed(
    self,
    text: str,
    strategy: ChunkStrategy = "fixed",
    metadata: dict | None = None,
) -> dict:
    """
    Chunk text using the specified strategy and prepare nodes for embedding.
    Embedding itself happens in Phase 2 (Qdrant integration).

    Returns: dict with strategy name and list of chunk texts + metadata.
    """
    from ingestion.chunkers import (
        fixed_chunker,
        sliding_chunker,
        semantic_chunker,
        parent_child_chunker,
        late_chunker,
    )

    chunker_map = {
        "fixed": fixed_chunker,
        "sliding": sliding_chunker,
        "semantic": semantic_chunker,
        "parent_child": parent_child_chunker,
        "late": late_chunker,
    }

    if strategy not in chunker_map:
        raise ValueError(f"Unknown chunking strategy: {strategy!r}. Choose from {list(chunker_map)}")

    try:
        chunker = chunker_map[strategy]
        nodes = chunker.chunk(text, metadata or {})
        logger.info(f"chunk_and_embed: {len(nodes)} nodes via '{strategy}' strategy")
        return {
            "strategy": strategy,
            "node_count": len(nodes),
            "chunks": [
                {"text": n.get_content(), "metadata": n.metadata}
                for n in nodes
            ],
        }
    except Exception as exc:
        logger.error(f"chunk_and_embed failed (strategy={strategy}): {exc}")
        raise self.retry(exc=exc, countdown=5)


@app.task(name="ingestion.pipeline.ingest_weather", bind=True, max_retries=3)
def ingest_weather(self, districts: list[str] | None = None, lookback_days: int = 7) -> int:
    """Fetch Open-Meteo weather data and write to TimescaleDB."""
    from ingestion.processors.weather_ingest import ingest_weather as _ingest

    try:
        written = asyncio.run(_ingest(districts=districts, lookback_days=lookback_days))
        logger.info(f"ingest_weather: {written} records written")
        return written
    except Exception as exc:
        logger.error(f"ingest_weather failed: {exc}")
        raise self.retry(exc=exc, countdown=30)


# ── High-level orchestration ─────────────────────────────────────────────────

@app.task(name="ingestion.pipeline.ingest_document", bind=True, max_retries=2)
def ingest_document(self, filepath: str | Path, strategy: ChunkStrategy = "fixed") -> dict:
    """
    Full ingestion chain: extract → tag → chunk → (embed in Phase 2).

    Registered as a Celery task so the API layer can dispatch it with
    `.delay(filepath, strategy)` and track progress via AsyncResult.

    Args:
        filepath: Path to the PDF file.
        strategy: Chunking strategy name.

    Returns:
        dict with extraction result, metadata, and chunk info.
    """
    filepath = str(filepath)
    logger.info(f"ingest_document: {filepath} (strategy={strategy})")

    # Step 1: Extract PDF
    extract_result = extract_pdf.apply(args=[filepath]).get()

    # Step 2: Tag metadata from first 4000 chars
    preview_text = extract_result["full_text"][:4000]
    meta_result = tag_metadata.apply(args=[preview_text]).get()

    # Step 3: Chunk with combined metadata
    chunk_result = chunk_and_embed.apply(
        args=[extract_result["full_text"], strategy, meta_result]
    ).get()

    return {
        "filepath": filepath,
        "extraction": {
            "total_pages": extract_result["total_pages"],
            "ocr_page_count": extract_result["ocr_page_count"],
        },
        "metadata": meta_result,
        "chunking": {
            "strategy": strategy,
            "node_count": chunk_result["node_count"],
        },
    }
