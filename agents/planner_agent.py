"""
Crop Planner Agent — generates seasonal crop planning recommendations.
Combines geo context (soil/district), semantic context, and crop constraints from crops.yaml.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import yaml
from loguru import logger

from config.gemini import call_gemini
from config.settings import settings
from knowledge.retrievers.geo_retriever import get_district_context, get_soil_context
from orchestration.state import AgentState

_CROPS_YAML: dict | None = None


def _get_crop_rules() -> dict:
    global _CROPS_YAML
    if _CROPS_YAML is None:
        with open(settings.crops_yaml, "r", encoding="utf-8") as f:
            _CROPS_YAML = yaml.safe_load(f)
    return _CROPS_YAML


PLANNER_PROMPT = """You are a crop planning specialist for Sri Lanka.

Farmer's query: {query}
Crop: {crop}
District: {district}
District profile: {district_context}
Soil profile: {soil_context}
Crop constraints (from agronomic rules): {crop_rules}

Knowledge base context:
{semantic_context}

Generate a practical seasonal crop plan. Return ONLY valid JSON:
{{
    "recommended_variety": "variety name and reason",
    "planting_window": "recommended planting period",
    "fertilizer_schedule": [
        {{"timing": "basal | top-dress 1 | top-dress 2", "product": "fertilizer name", "rate_kg_ha": 0.0}}
    ],
    "fertilizer_kg_ha": 0.0,
    "irrigation_advice": "irrigation scheduling guidance",
    "pest_prevention": ["preventive measures before crop establishment"],
    "expected_yield_t_ha": 0.0,
    "key_milestones": [
        {{"week": 1, "activity": "land preparation"}}
    ],
    "confidence": 0.0,
    "citations": ["source documents"]
}}"""


def _extract_json(text: str) -> dict:
    clean = re.sub(r"```(?:json)?\s*", "", text).strip().rstrip("`").strip()
    return json.loads(clean)


def planner_node(state: AgentState) -> AgentState:
    """Generate a crop plan using geo context, crop rules, and knowledge base."""
    trace = state.get("reasoning_trace", [])
    query = state.get("query", "")
    crop = state.get("crop", "paddy")
    district = state.get("district", "")

    # ── Geo context ──────────────────────────────────────────────────────────
    district_ctx = get_district_context(district) if district else {}
    soil_ctx = get_soil_context(district, crop) if district else []

    # ── Crop agronomic rules ─────────────────────────────────────────────────
    crop_rules = _get_crop_rules().get(crop, {})

    semantic_ctx = "\n---\n".join(state.get("semantic_context", [])[:5])

    try:
        raw = call_gemini(
            PLANNER_PROMPT.format(
                query=query,
                crop=crop,
                district=district or "unspecified",
                district_context=json.dumps(district_ctx, default=str),
                soil_context=json.dumps(soil_ctx[:2], default=str),
                crop_rules=json.dumps(crop_rules, default=str),
                semantic_context=semantic_ctx or "No knowledge base context available.",
            )
        )
        data = _extract_json(raw.strip())
    except Exception as exc:
        logger.error(f"planner_node: LLM call failed: {exc}")
        data = {
            "recommended_variety": "Consult local DOA office",
            "planting_window": "unknown",
            "fertilizer_schedule": [],
            "fertilizer_kg_ha": 0.0,
            "irrigation_advice": "Follow standard practices",
            "pest_prevention": [],
            "expected_yield_t_ha": 0.0,
            "key_milestones": [],
            "confidence": 0.0,
            "citations": [],
        }

    state["planner_recommendation"] = data
    state["geo_context"] = {"district": district_ctx, "soil": soil_ctx}
    state["confidence_score"] = float(data.get("confidence", 0.5))
    state["citations"] = state.get("citations", []) + data.get("citations", [])

    trace.append(
        f"Planner: variety={data.get('recommended_variety', 'N/A')}, "
        f"N={data.get('fertilizer_kg_ha', 0)} kg/ha, "
        f"yield={data.get('expected_yield_t_ha', 0)} t/ha"
    )
    state["reasoning_trace"] = trace

    logger.info(f"planner_node: plan generated for {crop} in {district}")
    return state
