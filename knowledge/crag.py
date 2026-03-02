"""
CRAG — Corrective Retrieval-Augmented Generation.

Grades each retrieved chunk against the query using Gemini 1.5 Flash.
Filters out irrelevant chunks and sets a web-fallback flag when
the knowledge base has insufficient relevant context.

Architecture rule: CRAG grading runs inside intent_node BEFORE any
specialist agent — never after.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from enum import Enum
from typing import Optional

import google.generativeai as genai
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

from config.settings import settings

genai.configure(api_key=settings.gemini_api_key)

RELEVANCE_THRESHOLD = 0.5  # chunks below this score are discarded

GRADER_PROMPT = """You are a relevance grader for an agricultural knowledge retrieval system.

Query: {query}
Chunk: {chunk}

Grade whether this chunk is relevant to the query. Return ONLY valid JSON:
{{
    "relevance": "relevant | partial | irrelevant",
    "score": 0.0,
    "reason": "one sentence explanation"
}}

Score guide:
  0.8–1.0 = directly answers the query
  0.5–0.79 = partially relevant, useful context
  0.0–0.49 = off-topic or unhelpful"""


class ChunkRelevance(str, Enum):
    RELEVANT = "relevant"
    PARTIAL = "partial"
    IRRELEVANT = "irrelevant"


@dataclass
class GradedChunk:
    chunk: str
    relevance: ChunkRelevance
    score: float
    reason: str


def _extract_json(text: str) -> dict:
    clean = re.sub(r"```(?:json)?\s*", "", text).strip().rstrip("`").strip()
    return json.loads(clean)


@retry(
    stop=stop_after_attempt(2),
    wait=wait_exponential(multiplier=2, min=1, max=10),
    reraise=False,
)
def _grade_single(model, query: str, chunk: str) -> GradedChunk:
    prompt = GRADER_PROMPT.format(query=query, chunk=chunk[:600])
    response = model.generate_content(prompt)
    data = _extract_json(response.text.strip())

    relevance_str = data.get("relevance", "partial")
    try:
        relevance = ChunkRelevance(relevance_str)
    except ValueError:
        relevance = ChunkRelevance.PARTIAL

    return GradedChunk(
        chunk=chunk,
        relevance=relevance,
        score=max(0.0, min(1.0, float(data.get("score", 0.5)))),
        reason=data.get("reason", ""),
    )


def grade_chunks(query: str, chunks: list[str]) -> list[GradedChunk]:
    """
    Grade a list of retrieved chunks for relevance to the query.

    Args:
        query: User query string.
        chunks: Candidate chunk texts (from reranker output).

    Returns:
        List of GradedChunk objects with relevance labels and scores.
    """
    if not chunks:
        return []

    model = genai.GenerativeModel(settings.gemini_model)
    graded: list[GradedChunk] = []

    for chunk in chunks:
        try:
            result = _grade_single(model, query, chunk)
            graded.append(result)
            logger.debug(
                f"CRAG grade: {result.relevance.value} "
                f"(score={result.score:.2f}) — {result.reason[:60]}"
            )
        except Exception as exc:
            logger.warning(f"CRAG grading failed for chunk: {exc}. Marking as partial.")
            graded.append(
                GradedChunk(
                    chunk=chunk,
                    relevance=ChunkRelevance.PARTIAL,
                    score=0.5,
                    reason="grading failed",
                )
            )

    return graded


def filter_relevant_chunks(
    graded: list[GradedChunk],
    threshold: float = RELEVANCE_THRESHOLD,
) -> tuple[Optional[list[str]], bool]:
    """
    Filter graded chunks above the relevance threshold.

    Args:
        graded: Output of grade_chunks().
        threshold: Minimum score to keep a chunk.

    Returns:
        (relevant_texts, needs_web_fallback)
        needs_web_fallback is True when no chunk passes the threshold.
    """
    relevant = [g for g in graded if g.score >= threshold]

    if not relevant:
        logger.warning(
            f"CRAG: 0/{len(graded)} chunks passed threshold {threshold}. "
            "Setting web_fallback=True."
        )
        return None, True

    texts = [g.chunk for g in sorted(relevant, key=lambda x: x.score, reverse=True)]
    logger.info(f"CRAG: {len(texts)}/{len(graded)} chunks kept (threshold={threshold})")
    return texts, False


def get_overall_grade(graded: list[GradedChunk]) -> str:
    """
    Derive an overall retrieval quality label from chunk grades.

    Returns: "CORRECT" | "AMBIGUOUS" | "INCORRECT"
    """
    if not graded:
        return "INCORRECT"

    relevant_count = sum(1 for g in graded if g.relevance == ChunkRelevance.RELEVANT)
    partial_count = sum(1 for g in graded if g.relevance == ChunkRelevance.PARTIAL)
    total = len(graded)

    if relevant_count / total >= 0.5:
        return "CORRECT"
    elif (relevant_count + partial_count) / total >= 0.3:
        return "AMBIGUOUS"
    return "INCORRECT"
