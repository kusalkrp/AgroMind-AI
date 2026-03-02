"""
CAG — Cache Augmented Generation.

Redis-backed semantic cache for full agent responses.
Architecture rule: CAG check is ALWAYS the first node in the LangGraph DAG.
"""
from __future__ import annotations

import hashlib
import json
from datetime import timedelta
from typing import Optional

import redis as redis_lib
from loguru import logger

from config.settings import settings

CACHE_TTL = timedelta(hours=24)
HIT_KEY = "cag:hit_count"
MISS_KEY = "cag:miss_count"

_redis: redis_lib.Redis | None = None


def _get_redis() -> redis_lib.Redis:
    global _redis
    if _redis is None:
        _redis = redis_lib.from_url(settings.redis_url, decode_responses=True)
    return _redis


# ── Key construction ──────────────────────────────────────────────────────────

def _cache_key(query: str, context_hash: str = "") -> str:
    """
    Build a deterministic cache key from query + optional context hash.
    Lowercases and strips the query so minor variations hit the same cache entry.
    """
    combined = f"{query.lower().strip()}:{context_hash}"
    digest = hashlib.sha256(combined.encode()).hexdigest()
    return f"cag:{digest}"


def _query_hash(query: str) -> str:
    """Normalised hash of the query alone (for simple cache lookups)."""
    return hashlib.md5(query.lower().strip().encode()).hexdigest()[:16]


# ── Public API ────────────────────────────────────────────────────────────────

def get_cached_response(
    query: str,
    context_hash: str = "",
) -> Optional[dict]:
    """
    Look up a cached agent response.

    Args:
        query: User query string.
        context_hash: Optional hash of filter context (district, crop) for
                      cache key disambiguation.

    Returns:
        Cached response dict, or None on a cache miss.
    """
    r = _get_redis()
    key = _cache_key(query, context_hash)
    try:
        cached = r.get(key)
        if cached:
            r.incr(HIT_KEY)
            logger.debug(f"CAG hit: {key[:20]}…")
            return json.loads(cached)
        r.incr(MISS_KEY)
        return None
    except Exception as exc:
        logger.warning(f"CAG get failed (Redis error): {exc}")
        return None


def cache_response(
    query: str,
    response: dict,
    context_hash: str = "",
    ttl: timedelta = CACHE_TTL,
) -> bool:
    """
    Store an agent response in the cache.

    Args:
        query: User query string.
        response: Response dict to cache (must be JSON-serialisable).
        context_hash: Optional context hash for key disambiguation.
        ttl: Cache time-to-live (default 24 hours).

    Returns:
        True on success, False on failure.
    """
    r = _get_redis()
    key = _cache_key(query, context_hash)
    try:
        r.setex(key, int(ttl.total_seconds()), json.dumps(response))
        logger.debug(f"CAG stored: {key[:20]}… (TTL={ttl})")
        return True
    except Exception as exc:
        logger.warning(f"CAG set failed (Redis error): {exc}")
        return False


def invalidate(query: str, context_hash: str = "") -> bool:
    """Delete a specific cache entry."""
    r = _get_redis()
    key = _cache_key(query, context_hash)
    try:
        deleted = r.delete(key)
        return bool(deleted)
    except Exception as exc:
        logger.warning(f"CAG invalidate failed: {exc}")
        return False


def get_cache_stats() -> dict:
    """Return current hit/miss counters and computed hit rate."""
    r = _get_redis()
    try:
        hits = int(r.get(HIT_KEY) or 0)
        misses = int(r.get(MISS_KEY) or 0)
        total = hits + misses
        return {
            "hit_count": hits,
            "miss_count": misses,
            "total_queries": total,
            "hit_rate": round(hits / total, 4) if total > 0 else 0.0,
        }
    except Exception as exc:
        logger.warning(f"CAG stats failed: {exc}")
        return {"hit_count": 0, "miss_count": 0, "total_queries": 0, "hit_rate": 0.0}


def flush_all_cache() -> int:
    """Delete all CAG cache keys (use with caution in production)."""
    r = _get_redis()
    keys = r.keys("cag:*")
    if keys:
        return r.delete(*keys)
    return 0
