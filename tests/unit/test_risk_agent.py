"""
Unit tests for agents/risk_agent.py (referenced in CLAUDE.md as canonical test pattern).

Mocks: Gemini API, temporal_retriever.
Tests: state mutation, risk level assignment, reasoning_trace appending.
"""
from unittest.mock import MagicMock, patch

import pytest

from orchestration.state import initial_state

# ── Sample data ───────────────────────────────────────────────────────────────

MOCK_WEATHER = {
    "district": "Kandy",
    "period_days": 30,
    "records": 28,
    "avg_temp_max_c": 30.2,
    "avg_temp_min_c": 19.8,
    "total_precipitation_mm": 45.3,
    "max_daily_precip_mm": 18.0,
    "drought_risk": False,
    "flood_risk": False,
    "heat_stress_risk": False,
    "daily_summary": [],
}

MOCK_RISK_RESPONSE = {
    "overall_risk_level": "medium",
    "risk_factors": [
        {"factor": "Blast Disease", "severity": "medium",
         "description": "High humidity favours blast", "mitigation": "Apply tricyclazole"}
    ],
    "disease_threats": ["Blast Disease", "Sheath Blight"],
    "pest_threats": ["Brown Plant Hopper"],
    "weather_risks": ["above-average humidity"],
    "recommended_actions": ["Scout fields weekly", "Apply fungicide preventively"],
    "confidence": 0.78,
    "citations": ["DOA Paddy Advisory 2024"],
}


def _make_state(**kwargs):
    state = initial_state(
        query="What is the disease risk for paddy in Kandy?",
        district="Kandy",
        crop="paddy",
    )
    state.update(kwargs)
    return state


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestRiskNode:

    def test_risk_node_sets_risk_assessment(self):
        """risk_node should populate state['risk_assessment'] with LLM output."""
        import json

        state = _make_state(semantic_context=["Paddy blast disease is common in wet areas."])

        mock_response = MagicMock()
        mock_response.text = json.dumps(MOCK_RISK_RESPONSE)

        with patch("agents.risk_agent.get_weather_risk_context", return_value=MOCK_WEATHER), \
             patch("agents.risk_agent.genai.GenerativeModel") as mock_model_cls:

            mock_model = MagicMock()
            mock_model.generate_content.return_value = mock_response
            mock_model_cls.return_value = mock_model

            from agents.risk_agent import risk_node
            result = risk_node(state)

        assert result["risk_assessment"] is not None
        assert result["risk_assessment"]["overall_risk_level"] == "medium"

    def test_risk_node_sets_risk_level_on_state(self):
        """risk_level field on state must match overall_risk_level from LLM."""
        import json

        state = _make_state(semantic_context=[])
        mock_response = MagicMock()
        mock_response.text = json.dumps(MOCK_RISK_RESPONSE)

        with patch("agents.risk_agent.get_weather_risk_context", return_value=MOCK_WEATHER), \
             patch("agents.risk_agent.genai.GenerativeModel") as mock_model_cls:

            mock_model = MagicMock()
            mock_model.generate_content.return_value = mock_response
            mock_model_cls.return_value = mock_model

            from agents.risk_agent import risk_node
            result = risk_node(state)

        assert result["risk_level"] == "medium"

    def test_risk_node_appends_to_reasoning_trace(self):
        """Every agent must append at least one entry to reasoning_trace."""
        import json

        state = _make_state(semantic_context=[], reasoning_trace=["Intent: disease"])
        mock_response = MagicMock()
        mock_response.text = json.dumps(MOCK_RISK_RESPONSE)

        with patch("agents.risk_agent.get_weather_risk_context", return_value=MOCK_WEATHER), \
             patch("agents.risk_agent.genai.GenerativeModel") as mock_model_cls:

            mock_model = MagicMock()
            mock_model.generate_content.return_value = mock_response
            mock_model_cls.return_value = mock_model

            from agents.risk_agent import risk_node
            result = risk_node(state)

        assert len(result["reasoning_trace"]) > 1
        assert any("Risk" in entry for entry in result["reasoning_trace"])

    def test_risk_node_sets_confidence_score(self):
        """confidence_score should come from the LLM output."""
        import json

        state = _make_state(semantic_context=[])
        mock_response = MagicMock()
        mock_response.text = json.dumps(MOCK_RISK_RESPONSE)

        with patch("agents.risk_agent.get_weather_risk_context", return_value=MOCK_WEATHER), \
             patch("agents.risk_agent.genai.GenerativeModel") as mock_model_cls:

            mock_model = MagicMock()
            mock_model.generate_content.return_value = mock_response
            mock_model_cls.return_value = mock_model

            from agents.risk_agent import risk_node
            result = risk_node(state)

        assert result["confidence_score"] == pytest.approx(0.78)

    def test_risk_node_sets_temporal_context(self):
        """temporal_context['weather'] should be populated from weather retriever."""
        import json

        state = _make_state(semantic_context=[])
        mock_response = MagicMock()
        mock_response.text = json.dumps(MOCK_RISK_RESPONSE)

        with patch("agents.risk_agent.get_weather_risk_context", return_value=MOCK_WEATHER), \
             patch("agents.risk_agent.genai.GenerativeModel") as mock_model_cls:

            mock_model = MagicMock()
            mock_model.generate_content.return_value = mock_response
            mock_model_cls.return_value = mock_model

            from agents.risk_agent import risk_node
            result = risk_node(state)

        assert result["temporal_context"].get("weather") == MOCK_WEATHER

    def test_risk_node_handles_llm_failure_gracefully(self):
        """If Gemini raises an exception, risk_node should return a safe default state."""
        state = _make_state(semantic_context=[])

        with patch("agents.risk_agent.get_weather_risk_context", return_value=MOCK_WEATHER), \
             patch("agents.risk_agent.genai.GenerativeModel") as mock_model_cls:

            mock_model = MagicMock()
            mock_model.generate_content.side_effect = Exception("API quota exceeded")
            mock_model_cls.return_value = mock_model

            from agents.risk_agent import risk_node
            result = risk_node(state)

        # Should not raise; should return a default risk assessment
        assert result["risk_assessment"] is not None
        assert result["risk_level"] in {"low", "medium", "high"}

    def test_risk_node_returns_agentstate_type(self):
        """risk_node must return a dict (AgentState)."""
        import json

        state = _make_state(semantic_context=[])
        mock_response = MagicMock()
        mock_response.text = json.dumps(MOCK_RISK_RESPONSE)

        with patch("agents.risk_agent.get_weather_risk_context", return_value=MOCK_WEATHER), \
             patch("agents.risk_agent.genai.GenerativeModel") as mock_model_cls:

            mock_model = MagicMock()
            mock_model.generate_content.return_value = mock_response
            mock_model_cls.return_value = mock_model

            from agents.risk_agent import risk_node
            result = risk_node(state)

        assert isinstance(result, dict)
        assert "query" in result
        assert "reasoning_trace" in result
