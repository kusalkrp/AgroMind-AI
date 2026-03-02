"""
Unit tests for api/routers/query.py

Uses FastAPI TestClient. Patches the LangGraph graph at its source module
(orchestration.agent_graph.get_graph) so no real services are required.
Both the lifespan pre-warm and the per-request import resolve to the mock.
"""
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# Fully-populated mock state that graph.invoke() returns
MOCK_GRAPH_RESULT = {
    "final_answer": "Apply 50 kg urea per hectare for paddy in Kandy.",
    "intent": "planning",
    "confidence_score": 0.82,
    "crag_grade": "CORRECT",
    "needs_web_fallback": False,
    "cache_hit": False,
    "risk_level": "low",
    "citations": ["DOA Advisory 2024"],
    "reasoning_trace": ["Intent: planning", "Planner: variety=BG 358", "Validation: PASSED"],
    "session_id": "test-session",
}


def _mock_graph(result=None, raise_exc=None):
    g = MagicMock()
    if raise_exc:
        g.invoke.side_effect = raise_exc
    else:
        g.invoke.return_value = result or MOCK_GRAPH_RESULT
    return g


class TestQueryEndpoint:

    def test_query_happy_path(self):
        """Valid POST → 200 with all QueryResponse fields present."""
        with patch("orchestration.agent_graph.get_graph", return_value=_mock_graph()):
            from api.main import app
            with TestClient(app) as c:
                resp = c.post(
                    "/api/v1/query",
                    json={"query": "What fertilizer for paddy in Kandy?",
                          "district": "Kandy", "crop": "paddy"},
                )
        assert resp.status_code == 200
        body = resp.json()
        for field in ["answer", "intent", "confidence", "crag_grade",
                      "needs_web_fallback", "cache_hit", "risk_level",
                      "citations", "reasoning_trace", "response_time_ms", "session_id"]:
            assert field in body, f"Missing field: {field}"

    def test_query_generates_session_id(self):
        """When session_id='' in body, response has a non-empty session_id."""
        with patch("orchestration.agent_graph.get_graph", return_value=_mock_graph()):
            from api.main import app
            with TestClient(app) as c:
                resp = c.post(
                    "/api/v1/query",
                    json={"query": "Paddy disease risk?", "session_id": ""},
                )
        assert resp.status_code == 200
        assert resp.json()["session_id"] != ""

    def test_query_uses_provided_session_id(self):
        """When session_id='abc' is given, response session_id == 'abc'."""
        with patch("orchestration.agent_graph.get_graph", return_value=_mock_graph()):
            from api.main import app
            with TestClient(app) as c:
                resp = c.post(
                    "/api/v1/query",
                    json={"query": "Market price query?", "session_id": "abc"},
                )
        assert resp.status_code == 200
        assert resp.json()["session_id"] == "abc"

    def test_query_graph_error_returns_500(self):
        """When graph.invoke raises, the endpoint returns 500."""
        with patch("orchestration.agent_graph.get_graph",
                   return_value=_mock_graph(raise_exc=RuntimeError("graph failed"))):
            from api.main import app
            with TestClient(app) as c:
                resp = c.post("/api/v1/query", json={"query": "Will this explode?"})
        assert resp.status_code == 500

    def test_query_response_time_positive(self):
        """response_time_ms should be >= 0."""
        with patch("orchestration.agent_graph.get_graph", return_value=_mock_graph()):
            from api.main import app
            with TestClient(app) as c:
                resp = c.post(
                    "/api/v1/query",
                    json={"query": "Any query that should succeed."},
                )
        assert resp.status_code == 200
        assert resp.json()["response_time_ms"] >= 0
