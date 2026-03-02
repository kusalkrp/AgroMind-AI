"""
LangGraph Redis checkpointer — persists agent state across turns for
multi-turn conversations and crash recovery.
"""
from __future__ import annotations

from loguru import logger

from config.settings import settings


_checkpointer = None


def _redis_has_json(url: str) -> bool:
    """Return True if the Redis server supports the RedisJSON module (JSON.SET)."""
    try:
        import redis as redis_lib
        r = redis_lib.from_url(url)
        r.execute_command("JSON.SET", "__agromind_test__", "$", '{"ok":1}')
        r.delete("__agromind_test__")
        return True
    except Exception:
        return False


def get_checkpointer():
    """
    Return a Redis-backed LangGraph checkpointer when RedisJSON is available,
    otherwise fall back to in-memory MemorySaver.
    """
    global _checkpointer
    if _checkpointer is not None:
        return _checkpointer

    if _redis_has_json(settings.redis_url):
        try:
            from langgraph.checkpoint.redis import RedisSaver  # type: ignore

            _cm = RedisSaver.from_conn_string(settings.redis_url)
            _checkpointer = _cm.__enter__()
            logger.info(f"LangGraph checkpointer: Redis+JSON ({settings.redis_url})")
            return _checkpointer
        except Exception as exc:
            logger.warning(f"RedisSaver init failed ({exc}). Falling back to MemorySaver.")
    else:
        logger.warning(
            "Redis server does not have RedisJSON module. "
            "Using in-memory MemorySaver for checkpointing. "
            "Switch to redis/redis-stack-server image for persistent checkpointing."
        )

    from langgraph.checkpoint.memory import MemorySaver  # type: ignore

    _checkpointer = MemorySaver()
    return _checkpointer
