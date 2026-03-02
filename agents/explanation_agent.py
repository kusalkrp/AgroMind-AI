"""
Explanation Agent — synthesises all agent outputs into a farmer-friendly,
multilingual final answer and caches it for future similar queries.

Supports: English, Sinhala, Tamil.
"""
from __future__ import annotations

import json

import google.generativeai as genai
from loguru import logger

from config.settings import settings
from knowledge.cag import cache_response
from orchestration.state import AgentState

genai.configure(api_key=settings.gemini_api_key)

EXPLAIN_PROMPT = """You are AgroMind, a friendly and knowledgeable agricultural advisor for Sri Lankan farmers.

Language to respond in: {language}
Farmer's query: {query}
Crop: {crop}
District: {district}

Agent findings summary:
- Risk assessment: {risk}
- Crop plan: {plan}
- Market insight: {market}
- Policy schemes: {policy}
- Validation warnings: {violations}
- Data confidence: {confidence}%

Write a clear, actionable response in {language}.

Guidelines:
- Use simple, practical language suitable for farmers
- For Sinhala/Tamil: write fully in that language; keep key technical terms in English in brackets
- Structure: (1) direct answer, (2) key risks to watch, (3) specific action steps, (4) confidence note
- If confidence < 0.5, advise the farmer to confirm with their local DOA extension officer
- Never give advice that contradicts the validation warnings
- Maximum 300 words"""


def explanation_node(state: AgentState) -> AgentState:
    """Generate the final multilingual answer and cache it."""
    trace = state.get("reasoning_trace", [])
    query = state.get("query", "")
    language = state.get("language", "english")
    crop = state.get("crop", "")
    district = state.get("district", "")
    confidence = state.get("confidence_score", 0.0)

    # If this is a cache hit, the final_answer is already set — just return
    if state.get("cache_hit") and state.get("final_answer"):
        trace.append("Explanation: served from CAG cache")
        state["reasoning_trace"] = trace
        return state

    # Summarise agent outputs for the prompt (keep concise to avoid token bloat)
    risk = state.get("risk_assessment") or {}
    plan = state.get("planner_recommendation") or {}
    market = state.get("market_insight") or {}
    policy_list = state.get("policy_matches") or []
    violations = state.get("validation_violations") or []

    risk_summary = {
        "level": risk.get("overall_risk_level"),
        "top_threats": (risk.get("disease_threats", []) + risk.get("pest_threats", []))[:3],
        "actions": risk.get("recommended_actions", [])[:3],
    }
    plan_summary = {
        "variety": plan.get("recommended_variety"),
        "planting_window": plan.get("planting_window"),
        "fertilizer_kg_ha": plan.get("fertilizer_kg_ha"),
        "expected_yield": plan.get("expected_yield_t_ha"),
    }
    market_summary = {
        "price_lkr_kg": market.get("current_price_lkr_per_kg"),
        "trend": market.get("price_trend"),
        "best_time": market.get("best_selling_time"),
    }
    policy_summary = [
        {"name": p.get("name"), "benefit": p.get("benefit")} for p in policy_list[:3]
    ]

    model = genai.GenerativeModel(settings.gemini_model)

    try:
        response = model.generate_content(
            EXPLAIN_PROMPT.format(
                language=language,
                query=query,
                crop=crop or "your crop",
                district=district or "your district",
                risk=json.dumps(risk_summary),
                plan=json.dumps(plan_summary),
                market=json.dumps(market_summary),
                policy=json.dumps(policy_summary),
                violations=json.dumps(violations),
                confidence=round(confidence * 100, 1),
            )
        )
        final_answer = response.text.strip()
    except Exception as exc:
        logger.error(f"explanation_node: LLM call failed: {exc}")
        final_answer = (
            "I encountered a technical issue generating your response. "
            "Please contact your local DOA extension officer for guidance."
        )

    state["final_answer"] = final_answer

    # ── Cache for future identical/similar queries ─────────────────────────────
    context_hash = f"{district}:{crop}"
    cache_response(
        query=query,
        response={
            "answer": final_answer,
            "confidence": confidence,
            "language": language,
        },
        context_hash=context_hash,
    )

    trace.append(
        f"Explanation: generated in {language} "
        f"(confidence={confidence:.0%}, cached=True)"
    )
    state["reasoning_trace"] = trace

    logger.info(f"explanation_node: answer generated ({language}, conf={confidence:.2f})")
    return state
