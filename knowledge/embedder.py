"""
Gemini gemini-embedding-001 wrapper.
Returns 3072-dimensional dense vectors for queries and document chunks.

Uses the new google-genai SDK (google.genai) which supports gemini-embedding-001.
"""
from __future__ import annotations

import time

from google import genai
from google.genai import types
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

from config.settings import settings

_client: genai.Client | None = None

EMBED_DIM = 3072
_BATCH_DELAY_S = 0.1  # small pause between batches to avoid 429s


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client(api_key=settings.gemini_api_key)
    return _client


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=2, max=20),
    reraise=True,
)
def embed_text(text: str) -> list[float]:
    """Embed a single text string. Returns a 3072-d float list."""
    client = _get_client()
    result = client.models.embed_content(
        model=settings.embedding_model,
        contents=text,
        config=types.EmbedContentConfig(task_type="RETRIEVAL_DOCUMENT"),
    )
    return list(result.embeddings[0].values)


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=2, max=20),
    reraise=True,
)
def embed_query(text: str) -> list[float]:
    """
    Embed a query string.
    Uses task_type='RETRIEVAL_QUERY' for asymmetric retrieval.
    """
    client = _get_client()
    result = client.models.embed_content(
        model=settings.embedding_model,
        contents=text,
        config=types.EmbedContentConfig(task_type="RETRIEVAL_QUERY"),
    )
    return list(result.embeddings[0].values)


def embed_batch(texts: list[str], batch_size: int = 20) -> list[list[float]]:
    """
    Embed a list of texts in batches to respect API rate limits.

    Args:
        texts: List of strings to embed.
        batch_size: Number of texts per API call.

    Returns:
        List of 3072-d embedding vectors in the same order as input.
    """
    client = _get_client()
    all_embeddings: list[list[float]] = []

    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        try:
            result = client.models.embed_content(
                model=settings.embedding_model,
                contents=batch,
                config=types.EmbedContentConfig(task_type="RETRIEVAL_DOCUMENT"),
            )
            all_embeddings.extend([list(e.values) for e in result.embeddings])
            logger.debug(f"Embedded batch {i // batch_size + 1}: {len(batch)} texts")
        except Exception as exc:
            logger.error(f"Batch embed failed at index {i}: {exc}")
            raise

        if i + batch_size < len(texts):
            time.sleep(_BATCH_DELAY_S)

    return all_embeddings
