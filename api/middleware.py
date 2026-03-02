"""
Prometheus middleware for AgroMind API.

Metrics are defined at module level so that hot-reloads (uvicorn --reload)
do not attempt to re-register already-registered metrics.
"""
from __future__ import annotations

import time

from prometheus_client import Counter, Histogram
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

# Module-level singleton metrics — defined once per process
REQUEST_COUNT = Counter(
    "agromind_requests_total",
    "Total HTTP requests received",
    ["endpoint", "status_code"],
)

REQUEST_LATENCY = Histogram(
    "agromind_request_duration_seconds",
    "HTTP request latency in seconds",
    ["endpoint"],
)


class PrometheusMiddleware(BaseHTTPMiddleware):
    """Record request count and latency for every HTTP request."""

    async def dispatch(self, request: Request, call_next):
        endpoint = request.url.path
        t0 = time.perf_counter()
        response = await call_next(request)
        latency = time.perf_counter() - t0
        REQUEST_COUNT.labels(
            endpoint=endpoint,
            status_code=str(response.status_code),
        ).inc()
        REQUEST_LATENCY.labels(endpoint=endpoint).observe(latency)
        return response
