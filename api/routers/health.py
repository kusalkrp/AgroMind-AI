"""
Health and metrics routers.

GET /health  — probes Qdrant, Redis, and PostgreSQL in parallel.
GET /metrics — serves Prometheus text-format metrics.
"""
from __future__ import annotations

import asyncio

from fastapi import APIRouter
from fastapi.responses import JSONResponse, PlainTextResponse
from loguru import logger
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from api.schemas import HealthResponse
from config.settings import settings

router = APIRouter()


# ── Service probes ─────────────────────────────────────────────────────────────

async def _check_qdrant() -> tuple[str, dict]:
    """Probe Qdrant: list collections and count points in the main collection."""
    try:
        from knowledge.retrievers.semantic_retriever import get_client

        client = get_client()
        loop = asyncio.get_event_loop()

        collections = await loop.run_in_executor(None, client.get_collections)
        col_names = [c.name for c in collections.collections]

        points = 0
        if settings.qdrant_collection in col_names:
            info = await loop.run_in_executor(
                None,
                lambda: client.get_collection(settings.qdrant_collection),
            )
            points = info.points_count or 0

        return "ok", {"status": "ok", "points": points}
    except Exception as exc:
        logger.warning(f"Qdrant health check failed: {exc}")
        return "error", {"status": "error", "error": str(exc)}


async def _check_redis() -> tuple[str, dict]:
    """Probe Redis with a PING."""
    try:
        import redis as redis_lib

        loop = asyncio.get_event_loop()
        r = redis_lib.from_url(settings.redis_url)
        await loop.run_in_executor(None, r.ping)
        return "ok", {"status": "ok"}
    except Exception as exc:
        logger.warning(f"Redis health check failed: {exc}")
        return "error", {"status": "error", "error": str(exc)}


async def _check_postgres() -> tuple[str, dict]:
    """Probe PostgreSQL with SELECT 1."""
    try:
        import psycopg2

        loop = asyncio.get_event_loop()

        def _connect() -> None:
            conn = psycopg2.connect(settings.postgres_url)
            cur = conn.cursor()
            cur.execute("SELECT 1")
            conn.close()

        await loop.run_in_executor(None, _connect)
        return "ok", {"status": "ok"}
    except Exception as exc:
        logger.warning(f"PostgreSQL health check failed: {exc}")
        return "error", {"status": "error", "error": str(exc)}


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/health", response_model=HealthResponse)
async def health():
    """Probe all backing services and return aggregate health status."""
    (qdrant_status, qdrant_info), (redis_status, redis_info), (pg_status, pg_info) = (
        await asyncio.gather(
            _check_qdrant(),
            _check_redis(),
            _check_postgres(),
        )
    )

    overall = (
        "ok"
        if all(s == "ok" for s in [qdrant_status, redis_status, pg_status])
        else "degraded"
    )

    from knowledge.cag import get_cache_stats

    cag_stats = get_cache_stats()

    body = HealthResponse(
        status=overall,
        services={
            "qdrant": qdrant_info,
            "redis": redis_info,
            "postgres": pg_info,
        },
        cag_stats=cag_stats,
        qdrant_points=qdrant_info.get("points", 0),
    )

    status_code = 200 if overall == "ok" else 503
    return JSONResponse(content=body.model_dump(), status_code=status_code)


@router.get("/metrics")
async def metrics():
    """Prometheus metrics in text format."""
    return PlainTextResponse(
        content=generate_latest().decode("utf-8"),
        media_type=CONTENT_TYPE_LATEST,
    )
