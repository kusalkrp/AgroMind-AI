"""
Unit tests for agents/planner_agent.py

Mocks: call_gemini, get_district_context, get_soil_context, _get_crop_rules
"""
import json
from unittest.mock import MagicMock, patch

import pytest

from orchestration.state import initial_state

MOCK_DISTRICT_CTX = {
    "district": "Kandy",
    "province": "Central",
    "elevation_m": 500,
    "rainfall_mm_annual": 2000,
}

MOCK_SOIL_CTX = [
    {"soil_type": "Reddish Brown Earths", "ph_value": 6.2, "texture": "loam"}
]

MOCK_CROP_RULES = {
    "max_nitrogen_kg_ha": 120,
    "ph_range": [5.5, 7.0],
    "suitable_seasons": ["maha", "yala"],
}

MOCK_PLANNER_RESPONSE = {
    "recommended_variety": "BG 358",
    "planting_window": "November–December (Maha season)",
    "fertilizer_schedule": [
        {"timing": "basal", "product": "Urea", "rate_kg_ha": 50.0}
    ],
    "fertilizer_kg_ha": 100.0,
    "irrigation_advice": "Maintain 5 cm standing water during vegetative stage.",
    "pest_prevention": ["Apply carbofuran at transplanting"],
    "expected_yield_t_ha": 5.2,
    "key_milestones": [{"week": 1, "activity": "land preparation"}],
    "confidence": 0.75,
    "citations": ["DOA Paddy Advisory 2024"],
}


def _make_state(**kwargs):
    state = initial_state(
        query="What variety should I plant in Kandy?",
        district="Kandy",
        crop="paddy",
    )
    state.update(kwargs)
    return state


class TestPlannerNode:

    def test_planner_populates_recommendation(self):
        """planner_node should set state['planner_recommendation']['recommended_variety']."""
        state = _make_state(semantic_context=["Paddy varieties for Kandy district."])

        with patch("agents.planner_agent.get_district_context",
                   return_value=MOCK_DISTRICT_CTX), \
             patch("agents.planner_agent.get_soil_context",
                   return_value=MOCK_SOIL_CTX), \
             patch("agents.planner_agent._get_crop_rules",
                   return_value={"paddy": MOCK_CROP_RULES}), \
             patch("agents.planner_agent.call_gemini",
                   return_value=json.dumps(MOCK_PLANNER_RESPONSE)):
            from agents.planner_agent import planner_node
            result = planner_node(state)

        assert result["planner_recommendation"] is not None
        assert result["planner_recommendation"]["recommended_variety"] == "BG 358"

    def test_planner_sets_geo_context(self):
        """District and soil data should be stored in state['geo_context']."""
        state = _make_state()

        with patch("agents.planner_agent.get_district_context",
                   return_value=MOCK_DISTRICT_CTX), \
             patch("agents.planner_agent.get_soil_context",
                   return_value=MOCK_SOIL_CTX), \
             patch("agents.planner_agent._get_crop_rules",
                   return_value={"paddy": MOCK_CROP_RULES}), \
             patch("agents.planner_agent.call_gemini",
                   return_value=json.dumps(MOCK_PLANNER_RESPONSE)):
            from agents.planner_agent import planner_node
            result = planner_node(state)

        assert "district" in result["geo_context"]
        assert "soil" in result["geo_context"]

    def test_planner_llm_failure_fallback(self):
        """When call_gemini raises, planner_recommendation must not be None and confidence==0.0."""
        state = _make_state()

        with patch("agents.planner_agent.get_district_context",
                   return_value=MOCK_DISTRICT_CTX), \
             patch("agents.planner_agent.get_soil_context",
                   return_value=MOCK_SOIL_CTX), \
             patch("agents.planner_agent._get_crop_rules",
                   return_value={"paddy": MOCK_CROP_RULES}), \
             patch("agents.planner_agent.call_gemini",
                   side_effect=Exception("LLM unavailable")):
            from agents.planner_agent import planner_node
            result = planner_node(state)

        assert result["planner_recommendation"] is not None
        assert result["confidence_score"] == pytest.approx(0.0)

    def test_planner_appends_reasoning_trace(self):
        """reasoning_trace should grow by at least 1 entry."""
        state = _make_state(reasoning_trace=["Intent: planning"])
        initial_len = len(state["reasoning_trace"])

        with patch("agents.planner_agent.get_district_context",
                   return_value=MOCK_DISTRICT_CTX), \
             patch("agents.planner_agent.get_soil_context",
                   return_value=MOCK_SOIL_CTX), \
             patch("agents.planner_agent._get_crop_rules",
                   return_value={"paddy": MOCK_CROP_RULES}), \
             patch("agents.planner_agent.call_gemini",
                   return_value=json.dumps(MOCK_PLANNER_RESPONSE)):
            from agents.planner_agent import planner_node
            result = planner_node(state)

        assert len(result["reasoning_trace"]) > initial_len
