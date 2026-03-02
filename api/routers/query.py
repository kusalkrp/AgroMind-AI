"""
Query router — POST /api/v1/query

Runs the full LangGraph agent pipeline and returns a structured response.
The graph is imported lazily so that API startup does not fail if a downstream
service is temporarily unavailable (the lifespan pre-warms it once all services
are ready).
"""
from __future__ import annotations

import asyncio
import time
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from loguru import logger

from api.schemas import QueryRequest, QueryResponse
from orchestration.state import initial_state

router = APIRouter()


@router.post("/query", response_model=QueryResponse)
async def query(request: QueryRequest):
    """Run the AgroMind agent pipeline on a natural-language agricultural query."""
    session_id = request.session_id or str(uuid4())

    state = initial_state(
        query=request.query,
        user_id=request.user_id,
        session_id=session_id,
        language=request.language,
        district=request.district,
        crop=request.crop,
    )

    # Lazy import — avoids import-time failures when services are still warming up
    from orchestration.agent_graph import get_graph

    graph = get_graph()
    config = {"configurable": {"thread_id": session_id}}

    t0 = time.perf_counter()
    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, graph.invoke, state, config)
    except Exception as exc:
        logger.error(f"Graph invocation failed (session={session_id}): {exc}")
        raise HTTPException(status_code=500, detail=str(exc))

    response_time_ms = (time.perf_counter() - t0) * 1000

    return QueryResponse(
        answer=result.get("final_answer") or "",
        intent=result.get("intent"),
        confidence=result.get("confidence_score", 0.0),
        crag_grade=result.get("crag_grade", "INCORRECT"),
        needs_web_fallback=result.get("needs_web_fallback", False),
        cache_hit=result.get("cache_hit", False),
        risk_level=result.get("risk_level", "low"),
        citations=result.get("citations", []),
        reasoning_trace=result.get("reasoning_trace", []),
        response_time_ms=response_time_ms,
        session_id=session_id,
        market_insight=result.get("market_insight"),
        risk_assessment=result.get("risk_assessment"),
    )
