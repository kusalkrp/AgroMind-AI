"""
Market Analyst Agent — provides crop price insights, selling advice,
and market trend analysis using TimescaleDB price history.
"""
from __future__ import annotations

import json
import re

from loguru import logger

from config.gemini import call_gemini
from config.settings import settings
from knowledge.retrievers.temporal_retriever import get_market_price_context
from orchestration.state import AgentState

MARKET_PROMPT = """You are an agricultural market analyst for Sri Lanka.

Farmer's query: {query}
Commodity: {commodity}
District: {district}

Recent market price data:
{price_context}

Knowledge base context (market reports, HARTI data):
{semantic_context}

Provide market insight and selling advice. Return ONLY valid JSON:
{{
    "current_price_lkr_per_kg": 0.0,
    "price_trend": "rising | falling | stable",
    "trend_explanation": "one sentence",
    "best_selling_time": "advice on when to sell",
    "best_market": "recommended market or buyer",
    "price_forecast_next_4_weeks": "brief price outlook",
    "profit_estimate_lkr_per_ha": 0.0,
    "selling_tips": ["actionable tips for maximising profit"],
    "risk_factors": ["market risk factors to watch"],
    "confidence": 0.0,
    "citations": ["data sources"]
}}"""


def _extract_json(text: str) -> dict:
    clean = re.sub(r"```(?:json)?\s*", "", text).strip().rstrip("`").strip()
    return json.loads(clean)


def market_node(state: AgentState) -> AgentState:
    """Provide market price analysis and selling recommendations."""
    trace = state.get("reasoning_trace", [])
    query = state.get("query", "")
    crop = state.get("crop", "paddy")
    district = state.get("district", "")

    # ── Temporal market context ───────────────────────────────────────────────
    price_ctx = get_market_price_context(commodity=crop, district=district, weeks=8)

    semantic_ctx = "\n---\n".join(state.get("semantic_context", [])[:5])

    try:
        raw = call_gemini(
            MARKET_PROMPT.format(
                query=query,
                commodity=crop,
                district=district or "nationwide",
                price_context=json.dumps(price_ctx, default=str),
                semantic_context=semantic_ctx or "No market reports available.",
            )
        )
        data = _extract_json(raw.strip())
    except Exception as exc:
        logger.error(f"market_node: LLM call failed: {exc}")
        data = {
            "current_price_lkr_per_kg": price_ctx.get("latest_price_lkr", 0.0),
            "price_trend": price_ctx.get("price_trend", "unknown"),
            "trend_explanation": "Data retrieval succeeded but analysis failed.",
            "best_selling_time": "Contact local HARTI office",
            "best_market": "Dambulla Economic Centre (if applicable)",
            "price_forecast_next_4_weeks": "unavailable",
            "profit_estimate_lkr_per_ha": 0.0,
            "selling_tips": [],
            "risk_factors": [],
            "confidence": 0.0,
            "citations": [],
        }

    state["market_insight"] = data
    state["temporal_context"] = {
        **state.get("temporal_context", {}),
        "market": price_ctx,
    }
    state["confidence_score"] = float(data.get("confidence", 0.5))
    state["citations"] = state.get("citations", []) + data.get("citations", [])

    trace.append(
        f"Market: {crop} trend={data.get('price_trend')} "
        f"@ LKR {data.get('current_price_lkr_per_kg', 'N/A')}/kg"
    )
    state["reasoning_trace"] = trace

    logger.info(f"market_node: {crop} price analysis complete")
    return state
