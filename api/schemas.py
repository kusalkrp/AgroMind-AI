"""
Pydantic request/response models for the AgroMind API.
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    query: str
    language: Literal["english", "sinhala", "tamil"] = "english"
    district: Optional[str] = None
    crop: Optional[str] = None
    user_id: str = "anonymous"
    session_id: str = ""


class QueryResponse(BaseModel):
    answer: str
    intent: Optional[str]
    confidence: float
    crag_grade: str
    needs_web_fallback: bool
    cache_hit: bool
    risk_level: str
    citations: list[str]
    reasoning_trace: list[str]
    response_time_ms: float
    session_id: str
    market_insight: Optional[dict] = None
    risk_assessment: Optional[dict] = None


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    services: dict
    cag_stats: dict
    qdrant_points: int


class IngestRequest(BaseModel):
    filepath: str
    strategy: str = "fixed"


class IngestResponse(BaseModel):
    task_id: str
    status: str
    message: str


class TaskStatusResponse(BaseModel):
    task_id: str
    state: str
    result: Optional[dict] = None
    error: Optional[str] = None
