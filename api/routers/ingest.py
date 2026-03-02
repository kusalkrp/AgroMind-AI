"""
Ingest router — /api/v1/ingest/*

Dispatches Celery tasks for document ingestion, weather data pulls, and web crawls.
All endpoints are fire-and-forget: they return a task_id immediately and the caller
can poll /api/v1/ingest/status/{task_id} for progress.
"""
from __future__ import annotations

from celery.result import AsyncResult
from fastapi import APIRouter, HTTPException
from loguru import logger

from api.schemas import IngestRequest, IngestResponse, TaskStatusResponse

router = APIRouter()


@router.post("/ingest/document", response_model=IngestResponse)
async def ingest_document_endpoint(request: IngestRequest):
    """Trigger the full document ingestion pipeline (extract → tag → chunk → embed)."""
    from ingestion.pipeline import ingest_document

    try:
        task = ingest_document.delay(request.filepath, request.strategy)
        return IngestResponse(
            task_id=task.id,
            status="PENDING",
            message=f"Document ingestion queued for {request.filepath!r}",
        )
    except Exception as exc:
        logger.error(f"Failed to queue ingest_document: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/ingest/weather", response_model=IngestResponse)
async def ingest_weather_endpoint():
    """Trigger weather data ingestion from Open-Meteo into TimescaleDB."""
    from ingestion.pipeline import ingest_weather

    try:
        task = ingest_weather.delay()
        return IngestResponse(
            task_id=task.id,
            status="PENDING",
            message="Weather ingestion queued",
        )
    except Exception as exc:
        logger.error(f"Failed to queue ingest_weather: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/ingest/crawl")
async def crawl_endpoint():
    """Trigger crawlers for DOA, HARTI, and market price sources."""
    from ingestion.pipeline import crawl_doa, crawl_harti, scrape_market

    try:
        tasks = [
            crawl_doa.delay(),
            crawl_harti.delay(),
            scrape_market.delay(),
        ]
        return {
            "task_ids": [t.id for t in tasks],
            "status": "PENDING",
            "message": "Crawl jobs queued for DOA, HARTI, and market prices",
        }
    except Exception as exc:
        logger.error(f"Failed to queue crawl tasks: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/ingest/status/{task_id}", response_model=TaskStatusResponse)
async def task_status(task_id: str):
    """Get the execution state of an async ingestion task."""
    async_result = AsyncResult(task_id)
    state = async_result.state

    result: dict | None = None
    error: str | None = None

    if state == "SUCCESS":
        raw = async_result.result
        result = raw if isinstance(raw, dict) else {"value": raw}
    elif state == "FAILURE":
        error = str(async_result.result)

    return TaskStatusResponse(
        task_id=task_id,
        state=state,
        result=result,
        error=error,
    )
