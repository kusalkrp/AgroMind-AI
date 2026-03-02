"""
Gemini text-embedding-004 wrapper.
Returns 768-dimensional dense vectors for queries and document chunks.
"""
from __future__ import annotations

import time
from typing import Union

import google.generativeai as genai
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

from config.settings import settings

genai.configure(api_key=settings.gemini_api_key)

EMBED_DIM = 768
_BATCH_DELAY_S = 0.1  # small pause between batches to avoid 429s


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=2, max=20),
    reraise=True,
)
def embed_text(text: str) -> list[float]:
    """Embed a single text string. Returns a 768-d float list."""
    result = genai.embed_content(
        model=settings.embedding_model,
        content=text,
        task_type="retrieval_document",
    )
    return result["embedding"]


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=2, max=20),
    reraise=True,
)
def embed_query(text: str) -> list[float]:
    """
    Embed a query string.
    Uses task_type='retrieval_query' for asymmetric retrieval.
    """
    result = genai.embed_content(
        model=settings.embedding_model,
        content=text,
        task_type="retrieval_query",
    )
    return result["embedding"]


def embed_batch(texts: list[str], batch_size: int = 20) -> list[list[float]]:
    """
    Embed a list of texts in batches to respect API rate limits.

    Args:
        texts: List of strings to embed.
        batch_size: Number of texts per API call (Gemini supports up to 100).

    Returns:
        List of 768-d embedding vectors in the same order as input.
    """
    all_embeddings: list[list[float]] = []

    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        try:
            result = genai.embed_content(
                model=settings.embedding_model,
                content=batch,
                task_type="retrieval_document",
            )
            embeddings = result["embedding"]
            # API returns a list of lists when given a list input
            if isinstance(embeddings[0], float):
                embeddings = [embeddings]
            all_embeddings.extend(embeddings)
            logger.debug(f"Embedded batch {i // batch_size + 1}: {len(batch)} texts")
        except Exception as exc:
            logger.error(f"Batch embed failed at index {i}: {exc}")
            raise

        if i + batch_size < len(texts):
            time.sleep(_BATCH_DELAY_S)

    return all_embeddings
