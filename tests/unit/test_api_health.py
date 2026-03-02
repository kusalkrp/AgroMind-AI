"""
Unit tests for api/routers/health.py

Uses FastAPI TestClient. Patches service probes and cache stats so no real
services are required.

Patch targets:
  - orchestration.agent_graph.get_graph  — prevents lifespan pre-warm from hitting services
  - api.routers.health._check_qdrant/redis/postgres — these ARE module-level coroutines
  - knowledge.cag.get_cache_stats        — imported locally inside health(), patch at source
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

OK_QDRANT = ("ok", {"status": "ok", "points": 4200})
OK_REDIS = ("ok", {"status": "ok"})
OK_POSTGRES = ("ok", {"status": "ok"})

ERROR_QDRANT = ("error", {"status": "error", "error": "Connection refused"})
ERROR_REDIS = ("error", {"status": "error", "error": "Connection refused"})
ERROR_POSTGRES = ("error", {"status": "error", "error": "Connection refused"})

MOCK_CAG_STATS = {
    "hit_count": 42,
    "miss_count": 8,
    "total_queries": 50,
    "hit_rate": 0.84,
}


def _health_client(qdrant=OK_QDRANT, redis=OK_REDIS, postgres=OK_POSTGRES):
    """Context manager that yields a TestClient with all health deps mocked."""
    return patch.multiple(
        "orchestration.agent_graph",
        get_graph=MagicMock(return_value=MagicMock()),
    ), patch.multiple(
        "api.routers.health",
        _check_qdrant=AsyncMock(return_value=qdrant),
        _check_redis=AsyncMock(return_value=redis),
        _check_postgres=AsyncMock(return_value=postgres),
    ), patch("knowledge.cag.get_cache_stats", return_value=MOCK_CAG_STATS)


class TestHealthEndpoint:

    def _get(self, qdrant=OK_QDRANT, redis=OK_REDIS, postgres=OK_POSTGRES):
        with patch("orchestration.agent_graph.get_graph", return_value=MagicMock()), \
             patch("api.routers.health._check_qdrant", new=AsyncMock(return_value=qdrant)), \
             patch("api.routers.health._check_redis", new=AsyncMock(return_value=redis)), \
             patch("api.routers.health._check_postgres", new=AsyncMock(return_value=postgres)), \
             patch("knowledge.cag.get_cache_stats", return_value=MOCK_CAG_STATS):
            from api.main import app
            with TestClient(app) as c:
                return c.get("/health")

    def test_health_all_ok(self):
        """All probes OK → 200, status=='ok'."""
        resp = self._get()
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_health_qdrant_down(self):
        """Qdrant probe error → 503, status=='degraded'."""
        resp = self._get(qdrant=ERROR_QDRANT)
        assert resp.status_code == 503
        assert resp.json()["status"] == "degraded"

    def test_health_redis_down(self):
        """Redis probe error → 503."""
        resp = self._get(redis=ERROR_REDIS)
        assert resp.status_code == 503

    def test_health_postgres_down(self):
        """PostgreSQL probe error → 503."""
        resp = self._get(postgres=ERROR_POSTGRES)
        assert resp.status_code == 503

    def test_health_includes_cag_stats(self):
        """Response body should have a 'cag_stats' key."""
        resp = self._get()
        assert "cag_stats" in resp.json()

    def test_health_qdrant_points_in_response(self):
        """Response body should have 'qdrant_points' key."""
        resp = self._get()
        assert "qdrant_points" in resp.json()

    def test_metrics_endpoint(self):
        """GET /metrics → 200 with Prometheus text body containing 'agromind_requests_total'."""
        with patch("orchestration.agent_graph.get_graph", return_value=MagicMock()):
            from api.main import app
            with TestClient(app) as c:
                resp = c.get("/metrics")
        assert resp.status_code == 200
        assert "agromind_requests_total" in resp.text
