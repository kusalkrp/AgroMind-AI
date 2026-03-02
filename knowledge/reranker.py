"""
Cross-encoder reranker — ms-marco-MiniLM-L-6-v2.
Takes query + candidate chunks from hybrid search and returns top-k re-scored results.
"""
from __future__ import annotations

from loguru import logger

_model = None


def _get_model():
    global _model
    if _model is None:
        try:
            from sentence_transformers import CrossEncoder  # type: ignore
            _model = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
            logger.debug("CrossEncoder loaded: ms-marco-MiniLM-L-6-v2")
        except ImportError:
            logger.warning(
                "sentence-transformers not installed — reranker disabled. "
                "Install it to enable cross-encoder reranking."
            )
            _model = None
    return _model


def rerank(
    query: str,
    chunks: list[str],
    top_k: int = 5,
) -> list[tuple[str, float]]:
    """
    Rerank chunks by relevance to the query using a cross-encoder.

    Args:
        query: The user query string.
        chunks: Candidate chunk texts from hybrid search.
        top_k: Number of top chunks to return.

    Returns:
        List of (chunk_text, score) tuples sorted descending by score.
    """
    if not chunks:
        return []

    model = _get_model()
    if model is None:
        # Graceful degradation: return top_k chunks with uniform score
        return [(c, 0.0) for c in chunks[:top_k]]

    pairs = [(query, chunk) for chunk in chunks]

    try:
        scores = model.predict(pairs).tolist()
    except Exception as exc:
        logger.error(f"reranker.predict failed: {exc}")
        return [(c, 0.0) for c in chunks[:top_k]]

    ranked = sorted(zip(chunks, scores), key=lambda x: x[1], reverse=True)
    return ranked[:top_k]


def rerank_texts(query: str, chunks: list[str], top_k: int = 5) -> list[str]:
    """Convenience wrapper that returns only the chunk texts (no scores)."""
    return [text for text, _ in rerank(query, chunks, top_k)]
