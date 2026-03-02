"""
Policy Matcher Agent — identifies relevant government schemes, subsidies,
insurance products, and regulations from the knowledge base.
"""
from __future__ import annotations

import json
import re

from loguru import logger

from config.gemini import call_gemini
from config.settings import settings
from orchestration.state import AgentState

POLICY_PROMPT = """You are an agricultural policy expert for Sri Lanka.

Farmer's query: {query}
Crop: {crop}
District: {district}

Relevant policy documents from knowledge base:
{semantic_context}

Identify applicable government schemes, subsidies, and regulations.
Return ONLY valid JSON:
{{
    "applicable_schemes": [
        {{
            "name": "scheme name",
            "type": "subsidy | insurance | loan | input_support | extension",
            "eligibility": "eligibility criteria",
            "benefit": "what the farmer receives",
            "how_to_apply": "application process",
            "deadline": "application deadline or 'rolling'",
            "source_document": "document name"
        }}
    ],
    "relevant_regulations": [
        {{
            "regulation": "regulation name",
            "implication": "how it affects the farmer",
            "compliance_action": "what farmer must do"
        }}
    ],
    "priority_recommendation": "most important scheme or action the farmer should take",
    "contact_office": "relevant government office and contact",
    "confidence": 0.0,
    "citations": ["policy document names"]
}}"""


def _extract_json(text: str) -> dict:
    clean = re.sub(r"```(?:json)?\s*", "", text).strip().rstrip("`").strip()
    return json.loads(clean)


def policy_node(state: AgentState) -> AgentState:
    """Match query to applicable government schemes and policies."""
    trace = state.get("reasoning_trace", [])
    query = state.get("query", "")
    crop = state.get("crop", "")
    district = state.get("district", "")

    semantic_ctx = "\n---\n".join(state.get("semantic_context", [])[:6])

    if not semantic_ctx:
        # No relevant policy docs retrieved — return empty result with note
        state["policy_matches"] = []
        state["confidence_score"] = 0.1
        trace.append("Policy: no relevant policy documents in knowledge base")
        state["reasoning_trace"] = trace
        return state

    try:
        raw = call_gemini(
            POLICY_PROMPT.format(
                query=query,
                crop=crop or "general",
                district=district or "national",
                semantic_context=semantic_ctx,
            )
        )
        data = _extract_json(raw.strip())
    except Exception as exc:
        logger.error(f"policy_node: LLM call failed: {exc}")
        data = {
            "applicable_schemes": [],
            "relevant_regulations": [],
            "priority_recommendation": "Contact your local Divisional Secretariat for scheme information.",
            "contact_office": "Ministry of Agriculture — 011 2186 346",
            "confidence": 0.0,
            "citations": [],
        }

    state["policy_matches"] = data.get("applicable_schemes", [])
    state["confidence_score"] = float(data.get("confidence", 0.5))
    state["citations"] = state.get("citations", []) + data.get("citations", [])

    n_schemes = len(data.get("applicable_schemes", []))
    trace.append(
        f"Policy: {n_schemes} applicable schemes found — "
        f"priority: {data.get('priority_recommendation', 'N/A')[:80]}"
    )
    state["reasoning_trace"] = trace

    logger.info(f"policy_node: {n_schemes} schemes matched for {crop} in {district}")
    return state
