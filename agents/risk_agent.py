"""
Risk Analyst Agent — assesses disease, pest, and weather risks for a crop/district.
Combines semantic context (knowledge base) with temporal weather context (TimescaleDB).
"""
from __future__ import annotations

import json
import re

from loguru import logger

from config.gemini import call_gemini
from config.settings import settings
from knowledge.retrievers.temporal_retriever import get_weather_risk_context
from orchestration.state import AgentState

RISK_PROMPT = """You are an expert agricultural risk analyst for Sri Lanka.

Crop: {crop}
District: {district}
Season: {season}

Recent weather data (last 30 days):
{weather_context}

Knowledge base context:
{semantic_context}

Analyse disease, pest, and weather risks. Return ONLY valid JSON:
{{
    "overall_risk_level": "low | medium | high",
    "risk_factors": [
        {{
            "factor": "factor name",
            "severity": "low | medium | high",
            "description": "description of risk",
            "mitigation": "recommended action"
        }}
    ],
    "disease_threats": ["list of specific disease threats this season"],
    "pest_threats": ["list of pest threats"],
    "weather_risks": ["list of weather-related risks"],
    "recommended_actions": ["ordered list of priority actions for the farmer"],
    "confidence": 0.0,
    "citations": ["source document names used"]
}}"""


def _extract_json(text: str) -> dict:
    clean = re.sub(r"```(?:json)?\s*", "", text).strip().rstrip("`").strip()
    return json.loads(clean)


def risk_node(state: AgentState) -> AgentState:
    """Assess crop risk using weather data + knowledge base context."""
    trace = state.get("reasoning_trace", [])
    crop = state.get("crop", "paddy")
    district = state.get("district", "Anuradhapura")
    season = state.get("sub_tasks", [])

    # ── Temporal context ─────────────────────────────────────────────────────
    weather = get_weather_risk_context(district=district, days_lookback=30)

    # ── LLM risk assessment ──────────────────────────────────────────────────
    semantic_ctx = "\n---\n".join(state.get("semantic_context", [])[:5])

    try:
        raw = call_gemini(
            RISK_PROMPT.format(
                crop=crop,
                district=district,
                season=", ".join(season) if season else "unknown",
                weather_context=json.dumps(weather, default=str),
                semantic_context=semantic_ctx or "No knowledge base context available.",
            )
        )
        data = _extract_json(raw.strip())
    except Exception as exc:
        logger.error(f"risk_node: LLM call failed: {exc}")
        data = {
            "overall_risk_level": "medium",
            "risk_factors": [],
            "disease_threats": [],
            "pest_threats": [],
            "weather_risks": [],
            "recommended_actions": ["Consult local agricultural extension officer"],
            "confidence": 0.0,
            "citations": [],
        }

    state["risk_assessment"] = data
    state["temporal_context"] = {"weather": weather}
    state["risk_level"] = data.get("overall_risk_level", "medium")
    state["confidence_score"] = float(data.get("confidence", 0.5))
    state["citations"] = data.get("citations", [])

    risk_level = data.get("overall_risk_level", "medium")
    n_factors = len(data.get("risk_factors", []))
    trace.append(
        f"Risk: {risk_level} — {n_factors} risk factors identified "
        f"(drought={weather.get('drought_risk')}, flood={weather.get('flood_risk')})"
    )
    state["reasoning_trace"] = trace

    logger.info(f"risk_node: {risk_level} risk for {crop} in {district}")
    return state
