"""
AgroMind AI — FastAPI application entry point.

Lifespan: pre-warms the LangGraph graph singleton at startup so the first
request does not incur cold-start latency (graph compilation + checkpointer
initialisation can take a few seconds).
"""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from loguru import logger

from api.middleware import PrometheusMiddleware
from api.routers.health import router as health_router
from api.routers.ingest import router as ingest_router
from api.routers.query import router as query_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Pre-warm the LangGraph singleton before accepting requests."""
    from orchestration.agent_graph import get_graph

    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, get_graph)
    logger.info("AgroMind API ready")
    yield


app = FastAPI(
    title="AgroMind AI",
    description="Agricultural Intelligence API for Sri Lanka",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(PrometheusMiddleware)

app.include_router(health_router)                    # GET /health, GET /metrics
app.include_router(query_router, prefix="/api/v1")   # POST /api/v1/query
app.include_router(ingest_router, prefix="/api/v1")  # POST /api/v1/ingest/*
