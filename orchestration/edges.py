"""
LangGraph edge routing functions.

These are pure functions — no LLM calls, no side effects.
They inspect AgentState and return string keys that LangGraph uses
to route to the next node.
"""
from __future__ import annotations

from orchestration.state import AgentState

MAX_RETRIES = 2


def route_by_intent(state: AgentState) -> str:
    """
    Route from the intent node to the appropriate specialist agent.

    Intent values:
      disease  → risk agent
      planning → planner agent
      market   → market agent
      policy   → policy agent
      general  → planner agent (default)
    """
    intent = state.get("intent", "general")
    route_map = {
        "disease": "risk",
        "planning": "planner",
        "market": "market",
        "policy": "policy",
        "general": "planner",
    }
    destination = route_map.get(intent, "planner")
    return destination


def route_after_cache(state: AgentState) -> str:
    """
    After the CAG cache check node:
      - Cache hit → skip all agents, go straight to explanation
      - Cache miss → proceed to intent classification
    """
    if state.get("cache_hit"):
        return "explanation"
    return "intent"


def should_retry(state: AgentState) -> str:
    """
    After validation, decide whether to retry the intent node or proceed.

    Retry conditions:
      - validation failed (violations found)
      - AND retry_count is below MAX_RETRIES

    Otherwise: pass through to explanation.
    """
    passed = state.get("validation_passed", False)
    retries = state.get("retry_count", 0)

    if not passed and retries < MAX_RETRIES:
        return "retry"
    return "pass"
