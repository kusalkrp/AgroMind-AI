"""
Unit tests for agents/market_agent.py

Mocks: call_gemini, get_market_price_context
"""
import json
from unittest.mock import MagicMock, patch

import pytest

from orchestration.state import initial_state

MOCK_PRICE_CTX = {
    "latest_price_lkr": 95.0,
    "price_trend": "rising",
    "records": [],
}

MOCK_MARKET_RESPONSE = {
    "current_price_lkr_per_kg": 95.0,
    "price_trend": "rising",
    "trend_explanation": "Seasonal demand increase after harvest.",
    "best_selling_time": "Within next 2 weeks before glut",
    "best_market": "Dambulla Economic Centre",
    "price_forecast_next_4_weeks": "Stable at LKR 90–100/kg",
    "profit_estimate_lkr_per_ha": 145000.0,
    "selling_tips": ["Grade your paddy before selling"],
    "risk_factors": ["weather delay"],
    "confidence": 0.82,
    "citations": ["HARTI Price Report 2024"],
}


def _make_state(**kwargs):
    state = initial_state(query="What is the paddy price?", district="Kandy", crop="paddy")
    state.update(kwargs)
    return state


class TestMarketNode:

    def test_market_populates_insight(self):
        """market_node should set state['market_insight']['current_price_lkr_per_kg']."""
        state = _make_state()

        with patch("agents.market_agent.get_market_price_context",
                   return_value=MOCK_PRICE_CTX), \
             patch("agents.market_agent.call_gemini",
                   return_value=json.dumps(MOCK_MARKET_RESPONSE)):
            from agents.market_agent import market_node
            result = market_node(state)

        assert result["market_insight"] is not None
        assert result["market_insight"]["current_price_lkr_per_kg"] == pytest.approx(95.0)

    def test_market_sets_confidence(self):
        """confidence_score should be > 0 after a successful LLM call."""
        state = _make_state()

        with patch("agents.market_agent.get_market_price_context",
                   return_value=MOCK_PRICE_CTX), \
             patch("agents.market_agent.call_gemini",
                   return_value=json.dumps(MOCK_MARKET_RESPONSE)):
            from agents.market_agent import market_node
            result = market_node(state)

        assert result["confidence_score"] > 0

    def test_market_stores_temporal_context(self):
        """Retriever dict should be stored in state['temporal_context']['market']."""
        state = _make_state()

        with patch("agents.market_agent.get_market_price_context",
                   return_value=MOCK_PRICE_CTX), \
             patch("agents.market_agent.call_gemini",
                   return_value=json.dumps(MOCK_MARKET_RESPONSE)):
            from agents.market_agent import market_node
            result = market_node(state)

        assert result["temporal_context"].get("market") == MOCK_PRICE_CTX

    def test_market_llm_failure_fallback(self):
        """When call_gemini raises, market_insight should still be non-None (fallback)."""
        state = _make_state()

        with patch("agents.market_agent.get_market_price_context",
                   return_value=MOCK_PRICE_CTX), \
             patch("agents.market_agent.call_gemini",
                   side_effect=Exception("API timeout")):
            from agents.market_agent import market_node
            result = market_node(state)

        assert result["market_insight"] is not None

    def test_market_appends_reasoning_trace(self):
        """reasoning_trace should grow by at least 1 entry."""
        state = _make_state(reasoning_trace=["Intent: market"])
        initial_len = len(state["reasoning_trace"])

        with patch("agents.market_agent.get_market_price_context",
                   return_value=MOCK_PRICE_CTX), \
             patch("agents.market_agent.call_gemini",
                   return_value=json.dumps(MOCK_MARKET_RESPONSE)):
            from agents.market_agent import market_node
            result = market_node(state)

        assert len(result["reasoning_trace"]) > initial_len
