"""
Intent Agent — classifies query intent and extracts agronomic entities,
then runs hybrid retrieval + reranking + CRAG grading.

Architecture rule: CRAG grading runs HERE, before any specialist agent.
"""
from __future__ import annotations

import json
import re

from loguru import logger

from config.gemini import call_gemini
from config.settings import settings
from knowledge.crag import filter_relevant_chunks, get_overall_grade, grade_chunks
from knowledge.reranker import rerank_texts
from knowledge.retrievers.semantic_retriever import hybrid_search
from orchestration.state import AgentState

INTENT_PROMPT = """You are an agricultural query classifier for Sri Lanka.

Classify the query intent and extract agronomic entities.
Return ONLY valid JSON — no markdown, no extra text:
{{
    "intent": "disease | planning | market | policy | general",
    "crop": "crop name in lowercase, or null",
    "district": "Sri Lanka district name, or null",
    "season": "Maha | Yala | null",
    "sub_tasks": ["list of specific sub-tasks needed to answer this query"],
    "reasoning": "one sentence explaining the classification"
}}

Intent definitions:
  disease  = pest, disease, blight, rot, insect damage, soil toxicity
  planning = planting schedule, fertilizer, variety selection, crop calendar
  market   = prices, selling, buying, market trends, profit
  policy   = subsidy, government scheme, insurance, regulation, permit
  general  = anything else

Query: {query}"""


def _extract_json(text: str) -> dict:
    clean = re.sub(r"```(?:json)?\s*", "", text).strip().rstrip("`").strip()
    return json.loads(clean)


def intent_node(state: AgentState) -> AgentState:
    """
    1. Classify intent and extract entities (crop, district, season)
    2. Run hybrid search with metadata filters
    3. Rerank top results
    4. Grade with CRAG
    5. Populate state with semantic_context, chunk_grades, crag_grade
    """
    query = state.get("query", "")
    trace = state.get("reasoning_trace", [])

    # ── Step 1: Intent classification ────────────────────────────────────────
    try:
        raw = call_gemini(INTENT_PROMPT.format(query=query))
        data = _extract_json(raw.strip())
    except Exception as exc:
        logger.error(f"intent_node: classification failed: {exc}")
        data = {"intent": "general", "crop": None, "district": None,
                "season": None, "sub_tasks": [], "reasoning": "classification failed"}

    intent = data.get("intent", "general")
    crop = data.get("crop") or state.get("crop")
    district = data.get("district") or state.get("district")
    season = data.get("season")

    state["intent"] = intent
    state["crop"] = crop
    state["district"] = district
    state["sub_tasks"] = data.get("sub_tasks", [])
    trace.append(f"Intent: {intent} — {data.get('reasoning', '')}")

    logger.info(f"intent_node: intent={intent} crop={crop} district={district}")

    # ── Step 2: Hybrid retrieval ─────────────────────────────────────────────
    filters: dict = {}
    if crop:
        filters["crop_types"] = [crop]
    if district:
        filters["district"] = district
    if season:
        filters["season"] = season

    raw_chunks = hybrid_search(query, filters=filters or None, top_k=15)

    # Fallback: metadata tags are sparse in practice — if filters return nothing,
    # retry without any filter so the vector search can still find relevant docs.
    if not raw_chunks and filters:
        logger.warning(
            f"intent_node: 0 chunks with filters {filters} — retrying without filters"
        )
        raw_chunks = hybrid_search(query, filters=None, top_k=15)

    # ── Step 3: Rerank ───────────────────────────────────────────────────────
    reranked = rerank_texts(query, raw_chunks, top_k=8)

    # ── Step 4: CRAG grading ─────────────────────────────────────────────────
    graded = grade_chunks(query, reranked)
    relevant_chunks, needs_fallback = filter_relevant_chunks(graded)
    crag_grade = get_overall_grade(graded)

    state["semantic_context"] = relevant_chunks or []
    state["needs_web_fallback"] = needs_fallback
    state["crag_grade"] = crag_grade
    state["chunk_grades"] = [
        {
            "chunk": g.chunk[:120],
            "score": g.score,
            "relevance": g.relevance.value,
        }
        for g in graded
    ]

    trace.append(
        f"CRAG: {crag_grade} — {len(state['semantic_context'])}/{len(graded)} chunks kept"
        + (" [web fallback]" if needs_fallback else "")
    )
    state["reasoning_trace"] = trace

    return state
