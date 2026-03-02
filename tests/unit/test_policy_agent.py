"""
Unit tests for agents/policy_agent.py

Mocks: call_gemini
"""
import json
from unittest.mock import MagicMock, patch

import pytest

from orchestration.state import initial_state

MOCK_POLICY_RESPONSE = {
    "applicable_schemes": [
        {
            "name": "Fertilizer Subsidy Programme",
            "type": "subsidy",
            "eligibility": "Registered paddy farmers",
            "benefit": "50% subsidy on urea and TSP",
            "how_to_apply": "Apply at nearest Agrarian Service Centre",
            "deadline": "rolling",
            "source_document": "MOA Circular 2024-05",
        },
        {
            "name": "Paddy Insurance Scheme",
            "type": "insurance",
            "eligibility": "Farmers growing ≥0.2 ha paddy",
            "benefit": "Crop loss compensation up to LKR 75,000/ha",
            "how_to_apply": "Register via Agrarian Insurance Board",
            "deadline": "Before planting",
            "source_document": "AIB Scheme Guidelines 2024",
        },
    ],
    "relevant_regulations": [],
    "priority_recommendation": "Apply for fertilizer subsidy immediately.",
    "contact_office": "Divisional Agrarian Services Centre",
    "confidence": 0.85,
    "citations": ["MOA Circular 2024-05"],
}


def _make_state(**kwargs):
    state = initial_state(
        query="What subsidies are available for paddy farmers?",
        district="Kandy",
        crop="paddy",
    )
    state.update(kwargs)
    return state


class TestPolicyNode:

    def test_policy_matches_schemes(self):
        """LLM returns 2 applicable_schemes → len(state['policy_matches'])==2."""
        state = _make_state(semantic_context=["DOA fertilizer subsidy circular."])

        with patch("agents.policy_agent.call_gemini",
                   return_value=json.dumps(MOCK_POLICY_RESPONSE)):
            from agents.policy_agent import policy_node
            result = policy_node(state)

        assert len(result["policy_matches"]) == 2

    def test_policy_empty_context_early_exit(self):
        """With semantic_context=[], policy_matches==[], confidence==0.1, call_gemini NOT called."""
        state = _make_state(semantic_context=[])
        mock_gemini = MagicMock()

        with patch("agents.policy_agent.call_gemini", mock_gemini):
            from agents.policy_agent import policy_node
            result = policy_node(state)

        assert result["policy_matches"] == []
        assert result["confidence_score"] == pytest.approx(0.1)
        mock_gemini.assert_not_called()

    def test_policy_llm_failure_returns_empty(self):
        """When call_gemini raises, policy_matches should be []."""
        state = _make_state(semantic_context=["Some policy document."])

        with patch("agents.policy_agent.call_gemini",
                   side_effect=Exception("API error")):
            from agents.policy_agent import policy_node
            result = policy_node(state)

        assert result["policy_matches"] == []

    def test_policy_appends_reasoning_trace(self):
        """reasoning_trace should grow by at least 1 entry."""
        state = _make_state(
            semantic_context=["MOA fertilizer subsidy document."],
            reasoning_trace=["Intent: policy"],
        )
        initial_len = len(state["reasoning_trace"])

        with patch("agents.policy_agent.call_gemini",
                   return_value=json.dumps(MOCK_POLICY_RESPONSE)):
            from agents.policy_agent import policy_node
            result = policy_node(state)

        assert len(result["reasoning_trace"]) > initial_len
