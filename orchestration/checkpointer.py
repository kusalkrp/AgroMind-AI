"""
LangGraph Redis checkpointer — persists agent state across turns for
multi-turn conversations and crash recovery.
"""
from __future__ import annotations

from loguru import logger

from config.settings import settings


def get_checkpointer():
    """
    Return a Redis-backed LangGraph checkpointer.

    Falls back to an in-memory checkpointer if Redis is unavailable
    (e.g. during unit tests).
    """
    try:
        from langgraph.checkpoint.redis import RedisSaver  # type: ignore

        checkpointer = RedisSaver.from_conn_string(settings.redis_url)
        logger.info(f"LangGraph checkpointer: Redis ({settings.redis_url})")
        return checkpointer
    except Exception as exc:
        logger.warning(
            f"Redis checkpointer unavailable ({exc}). "
            "Falling back to in-memory MemorySaver."
        )
        from langgraph.checkpoint.memory import MemorySaver  # type: ignore

        return MemorySaver()
