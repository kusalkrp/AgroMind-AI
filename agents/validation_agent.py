"""
Validation Agent — enforces agronomic hard limits from crops.yaml.

Architecture rule: hard-limit checks use crops.yaml rules, NOT LLM judgment.
LLM is only called for soft/contextual checks (citation plausibility).
"""
from __future__ import annotations

from typing import Optional

import yaml
from loguru import logger

from config.settings import settings
from orchestration.state import AgentState

_CROP_RULES: dict | None = None


def _get_crop_rules() -> dict:
    global _CROP_RULES
    if _CROP_RULES is None:
        with open(settings.crops_yaml, "r", encoding="utf-8") as f:
            _CROP_RULES = yaml.safe_load(f)
    return _CROP_RULES


def _check_nitrogen_limit(crop: str, planner_rec: dict, violations: list[str]) -> None:
    """Hard limit: nitrogen application must not exceed crops.yaml max_nitrogen_kg_ha."""
    rules = _get_crop_rules().get(crop, {})
    max_n = rules.get("max_nitrogen_kg_ha")
    if max_n is None:
        return

    recommended_n = planner_rec.get("fertilizer_kg_ha", 0.0)
    if recommended_n and float(recommended_n) > max_n:
        violations.append(
            f"Nitrogen recommendation ({recommended_n} kg/ha) exceeds safe limit "
            f"({max_n} kg/ha) for {crop}. Reduce to {max_n} kg/ha."
        )


def _check_ph_suitability(crop: str, soil_ctx: list[dict], violations: list[str]) -> None:
    """Warn if soil pH is outside the crop's suitable range."""
    rules = _get_crop_rules().get(crop, {})
    ph_range = rules.get("ph_range")
    if not ph_range or not soil_ctx:
        return

    ph_min, ph_max = ph_range
    for soil in soil_ctx:
        ph = soil.get("ph_value")
        if ph is not None and not (ph_min <= float(ph) <= ph_max):
            violations.append(
                f"Soil pH {ph} is outside the recommended range [{ph_min}–{ph_max}] "
                f"for {crop}. Soil amendment required before planting."
            )


def _check_season_validity(
    crop: str,
    season: Optional[str],
    violations: list[str],
) -> None:
    """Warn if a planting season is not suitable for the crop."""
    if not season:
        return
    rules = _get_crop_rules().get(crop, {})
    suitable = rules.get("suitable_seasons", [])
    if suitable and season not in suitable:
        violations.append(
            f"Season '{season}' is not in the suitable seasons {suitable} for {crop}."
        )


def _adjust_confidence(
    base_confidence: float,
    violations: list[str],
) -> float:
    """Reduce confidence proportionally to the number of violations."""
    if not violations:
        return round(base_confidence, 2)
    penalty = 0.15 * len(violations)
    return round(max(0.0, base_confidence - penalty), 2)


def validation_node(state: AgentState) -> AgentState:
    """
    Run deterministic agronomic rule checks on agent outputs.
    Sets validation_passed, validation_violations, and adjusts confidence_score.
    Increments retry_count so should_retry can gate re-runs.
    """
    trace = state.get("reasoning_trace", [])
    violations: list[str] = []

    crop = state.get("crop", "")
    planner_rec = state.get("planner_recommendation") or {}
    geo_ctx = state.get("geo_context", {})
    soil_ctx = geo_ctx.get("soil", []) if isinstance(geo_ctx, dict) else []

    # ── Hard-limit checks (no LLM) ────────────────────────────────────────────
    if crop:
        _check_nitrogen_limit(crop, planner_rec, violations)
        _check_ph_suitability(crop, soil_ctx, violations)

        # Extract season from sub_tasks or state
        season = None
        for task in state.get("sub_tasks", []):
            if "maha" in task.lower():
                season = "Maha"
            elif "yala" in task.lower():
                season = "Yala"
        _check_season_validity(crop, season, violations)

    # ── Confidence adjustment ─────────────────────────────────────────────────
    base_confidence = state.get("confidence_score", 0.5)
    adjusted_confidence = _adjust_confidence(base_confidence, violations)

    state["validation_violations"] = violations
    state["validation_passed"] = len(violations) == 0
    state["confidence_score"] = adjusted_confidence
    state["retry_count"] = state.get("retry_count", 0) + 1

    if violations:
        trace.append(
            f"Validation: FAILED — {len(violations)} violation(s): "
            + "; ".join(violations[:2])
        )
        logger.warning(f"validation_node: {len(violations)} violations for {crop}")
    else:
        trace.append("Validation: PASSED — all agronomic limits within bounds")
        logger.info(f"validation_node: passed for {crop}")

    state["reasoning_trace"] = trace
    return state
