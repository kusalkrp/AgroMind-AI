"""
Unit tests for agents/validation_agent.py

No LLM — all deterministic rule checks from crops.yaml (mocked).
"""
from unittest.mock import patch

import pytest

from orchestration.state import initial_state

MOCK_CROP_RULES = {
    "paddy": {
        "max_nitrogen_kg_ha": 120,
        "ph_range": [5.5, 7.0],
        "suitable_seasons": ["maha", "yala"],
    }
}


def _make_state(**kwargs):
    state = initial_state(query="test", district="Kandy", crop="paddy")
    # Default planner recommendation
    state["planner_recommendation"] = {
        "fertilizer_kg_ha": 100.0,
        "recommended_variety": "BG 358",
    }
    state["confidence_score"] = 0.8
    state.update(kwargs)
    return state


def _with_rules(fn):
    """Decorator-free helper: patch _get_crop_rules globally for validation_agent."""
    pass


class TestValidationNode:

    def test_validation_passes_valid_plan(self):
        """N=100, pH=6.5, no sub_tasks → season stays None → passes with no violations."""
        state = _make_state(
            planner_recommendation={"fertilizer_kg_ha": 100.0},
            geo_context={"soil": [{"ph_value": 6.5}]},
            sub_tasks=[],  # no season extracted → _check_season_validity skips
            confidence_score=0.8,
        )

        with patch("agents.validation_agent._get_crop_rules", return_value=MOCK_CROP_RULES):
            from agents.validation_agent import validation_node
            result = validation_node(state)

        assert result["validation_passed"] is True
        assert result["validation_violations"] == []

    def test_validation_fails_nitrogen_excess(self):
        """N=200 exceeds max 120 kg/ha → violation list non-empty, validation_passed=False."""
        state = _make_state(
            planner_recommendation={"fertilizer_kg_ha": 200.0},
            geo_context={"soil": []},
        )

        with patch("agents.validation_agent._get_crop_rules", return_value=MOCK_CROP_RULES):
            from agents.validation_agent import validation_node
            result = validation_node(state)

        assert result["validation_passed"] is False
        assert len(result["validation_violations"]) > 0

    def test_validation_fails_ph_out_of_range(self):
        """pH=4.0 is below range [5.5, 7.0] → violation about pH."""
        state = _make_state(
            planner_recommendation={"fertilizer_kg_ha": 100.0},
            geo_context={"soil": [{"ph_value": 4.0}]},
        )

        with patch("agents.validation_agent._get_crop_rules", return_value=MOCK_CROP_RULES):
            from agents.validation_agent import validation_node
            result = validation_node(state)

        assert result["validation_passed"] is False
        ph_violation = any("pH" in v or "ph" in v.lower() for v in result["validation_violations"])
        assert ph_violation

    def test_validation_adjusts_confidence_per_violation(self):
        """2 violations reduce confidence by 2*0.15=0.30."""
        # Trigger both N and pH violations
        state = _make_state(
            planner_recommendation={"fertilizer_kg_ha": 250.0},
            geo_context={"soil": [{"ph_value": 4.0}]},
            confidence_score=0.8,
        )

        with patch("agents.validation_agent._get_crop_rules", return_value=MOCK_CROP_RULES):
            from agents.validation_agent import validation_node
            result = validation_node(state)

        violations = result["validation_violations"]
        assert len(violations) >= 2
        expected = round(max(0.0, 0.8 - 0.15 * len(violations)), 2)
        assert result["confidence_score"] == pytest.approx(expected)

    def test_validation_increments_retry_count(self):
        """retry_count should increment from 0 to 1."""
        state = _make_state(retry_count=0)

        with patch("agents.validation_agent._get_crop_rules", return_value=MOCK_CROP_RULES):
            from agents.validation_agent import validation_node
            result = validation_node(state)

        assert result["retry_count"] == 1

    def test_validation_appends_reasoning_trace(self):
        """reasoning_trace should grow by at least 1 entry."""
        state = _make_state(reasoning_trace=["Intent: planning"])
        initial_len = len(state["reasoning_trace"])

        with patch("agents.validation_agent._get_crop_rules", return_value=MOCK_CROP_RULES):
            from agents.validation_agent import validation_node
            result = validation_node(state)

        assert len(result["reasoning_trace"]) > initial_len
