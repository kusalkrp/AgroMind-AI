"""
Unit tests for agents/explanation_agent.py

Mocks: call_gemini, cache_response
"""
from unittest.mock import MagicMock, patch

import pytest

from orchestration.state import initial_state


def _make_state(**kwargs):
    state = initial_state(
        query="What fertilizer for paddy in Kandy?",
        district="Kandy",
        crop="paddy",
    )
    state["confidence_score"] = 0.75
    state.update(kwargs)
    return state


class TestExplanationNode:

    def test_explanation_generates_answer(self):
        """LLM returning a string sets state['final_answer']."""
        state = _make_state()

        with patch("agents.explanation_agent.call_gemini",
                   return_value="Apply 50 kg urea per hectare at transplanting."), \
             patch("agents.explanation_agent.cache_response"):
            from agents.explanation_agent import explanation_node
            result = explanation_node(state)

        assert result["final_answer"] is not None
        assert len(result["final_answer"]) > 0

    def test_explanation_cache_hit_skips_llm(self):
        """When cache_hit=True and final_answer is already set, call_gemini is NOT called."""
        state = _make_state(cache_hit=True, final_answer="cached answer")
        mock_gemini = MagicMock()

        with patch("agents.explanation_agent.call_gemini", mock_gemini), \
             patch("agents.explanation_agent.cache_response"):
            from agents.explanation_agent import explanation_node
            result = explanation_node(state)

        mock_gemini.assert_not_called()
        assert result["final_answer"] == "cached answer"

    def test_explanation_caches_new_response(self):
        """cache_response should be called exactly once after a successful LLM call."""
        state = _make_state()
        mock_cache = MagicMock()

        with patch("agents.explanation_agent.call_gemini",
                   return_value="Apply fertilizer as recommended."), \
             patch("agents.explanation_agent.cache_response", mock_cache):
            from agents.explanation_agent import explanation_node
            explanation_node(state)

        mock_cache.assert_called_once()

    def test_explanation_llm_failure_fallback(self):
        """When call_gemini raises, final_answer should contain fallback text (not empty)."""
        state = _make_state()

        with patch("agents.explanation_agent.call_gemini",
                   side_effect=Exception("rate limit")), \
             patch("agents.explanation_agent.cache_response"):
            from agents.explanation_agent import explanation_node
            result = explanation_node(state)

        assert result["final_answer"] is not None
        assert len(result["final_answer"]) > 0

    def test_explanation_appends_reasoning_trace(self):
        """reasoning_trace should grow by at least 1 entry."""
        state = _make_state(reasoning_trace=["Intent: planning", "Validation: PASSED"])
        initial_len = len(state["reasoning_trace"])

        with patch("agents.explanation_agent.call_gemini",
                   return_value="Your paddy plan for Kandy is ready."), \
             patch("agents.explanation_agent.cache_response"):
            from agents.explanation_agent import explanation_node
            result = explanation_node(state)

        assert len(result["reasoning_trace"]) > initial_len
