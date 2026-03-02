"""
AgentState — the shared TypedDict passed between all LangGraph nodes.

Architecture rule: all agents receive this state, mutate relevant fields,
append to reasoning_trace, and return the mutated state.
"""
from __future__ import annotations

from typing import Literal, Optional, TypedDict


class AgentState(TypedDict, total=False):
    # ── Input ────────────────────────────────────────────────────────────────
    query: str
    user_id: str
    session_id: str
    district: Optional[str]
    crop: Optional[str]
    language: Literal["english", "sinhala", "tamil"]

    # ── Routing ──────────────────────────────────────────────────────────────
    intent: Optional[str]       # disease | planning | market | policy | general
    sub_tasks: list[str]

    # ── Retrieved context ────────────────────────────────────────────────────
    semantic_context: list[str]         # chunk texts from hybrid search
    temporal_context: dict              # weather + market data from TimescaleDB
    geo_context: dict                   # district + soil info from PostGIS

    # ── CRAG state ───────────────────────────────────────────────────────────
    chunk_grades: list[dict]            # [{chunk, score, relevance}, ...]
    crag_grade: str                     # CORRECT | AMBIGUOUS | INCORRECT
    needs_web_fallback: bool

    # ── Agent outputs ─────────────────────────────────────────────────────────
    risk_assessment: Optional[dict]
    planner_recommendation: Optional[dict]
    market_insight: Optional[dict]
    policy_matches: list[dict]

    # ── Validation ───────────────────────────────────────────────────────────
    validation_passed: bool
    validation_violations: list[str]
    retry_count: int

    # ── Final output ─────────────────────────────────────────────────────────
    confidence_score: float
    risk_level: Literal["low", "medium", "high"]
    final_answer: Optional[str]
    citations: list[str]
    reasoning_trace: list[str]

    # ── Cache ────────────────────────────────────────────────────────────────
    cache_hit: bool
    response_time_ms: float


def initial_state(
    query: str,
    user_id: str = "anonymous",
    session_id: str = "",
    language: str = "english",
    district: Optional[str] = None,
    crop: Optional[str] = None,
) -> AgentState:
    """Build a default AgentState for a new query."""
    import uuid

    return AgentState(
        query=query,
        user_id=user_id,
        session_id=session_id or str(uuid.uuid4()),
        district=district,
        crop=crop,
        language=language,  # type: ignore[arg-type]
        intent=None,
        sub_tasks=[],
        semantic_context=[],
        temporal_context={},
        geo_context={},
        chunk_grades=[],
        crag_grade="INCORRECT",
        needs_web_fallback=False,
        risk_assessment=None,
        planner_recommendation=None,
        market_insight=None,
        policy_matches=[],
        validation_passed=False,
        validation_violations=[],
        retry_count=0,
        confidence_score=0.0,
        risk_level="low",
        final_answer=None,
        citations=[],
        reasoning_trace=[],
        cache_hit=False,
        response_time_ms=0.0,
    )
