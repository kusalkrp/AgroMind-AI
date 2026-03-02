"""
LangGraph Agent Graph — the main DAG wiring all nodes together.

Flow:
  cache_check → (hit) → explanation → END
              → (miss) → intent → {risk|planner|market|policy}
                               → validation → (pass) → explanation → END
                                           → (retry) → intent → …
"""
from __future__ import annotations

from loguru import logger

from orchestration.edges import route_after_cache, route_by_intent, should_retry
from orchestration.state import AgentState


def _build_cache_check_node():
    from knowledge.cag import get_cached_response

    def cache_check_node(state: AgentState) -> AgentState:
        query = state.get("query", "")
        district = state.get("district", "")
        crop = state.get("crop", "")
        context_hash = f"{district}:{crop}"

        cached = get_cached_response(query, context_hash)
        if cached:
            state["cache_hit"] = True
            state["final_answer"] = cached.get("answer")
            state["confidence_score"] = cached.get("confidence", 0.0)
            state["reasoning_trace"] = state.get("reasoning_trace", []) + [
                "CAG: cache hit — skipping agent pipeline"
            ]
            logger.info(f"CAG hit for query: {query[:60]!r}")
        else:
            state["cache_hit"] = False

        return state

    return cache_check_node


def build_graph():
    """
    Compile and return the LangGraph CompiledStateGraph.

    Imports agents lazily to avoid circular imports at module load time.
    """
    from langgraph.graph import END, StateGraph  # type: ignore

    from agents.explanation_agent import explanation_node
    from agents.intent_agent import intent_node
    from agents.market_agent import market_node
    from agents.planner_agent import planner_node
    from agents.policy_agent import policy_node
    from agents.risk_agent import risk_node
    from agents.validation_agent import validation_node
    from orchestration.checkpointer import get_checkpointer

    workflow = StateGraph(AgentState)

    # ── Nodes ────────────────────────────────────────────────────────────────
    workflow.add_node("cache_check", _build_cache_check_node())
    workflow.add_node("intent", intent_node)
    workflow.add_node("risk", risk_node)
    workflow.add_node("planner", planner_node)
    workflow.add_node("market", market_node)
    workflow.add_node("policy", policy_node)
    workflow.add_node("validation", validation_node)
    workflow.add_node("explanation", explanation_node)

    # ── Entry point ───────────────────────────────────────────────────────────
    workflow.set_entry_point("cache_check")

    # ── Edges ─────────────────────────────────────────────────────────────────
    # After cache check: hit → explanation, miss → intent
    workflow.add_conditional_edges(
        "cache_check",
        route_after_cache,
        {"explanation": "explanation", "intent": "intent"},
    )

    # After intent: route to specialist agent
    workflow.add_conditional_edges(
        "intent",
        route_by_intent,
        {
            "risk": "risk",
            "planner": "planner",
            "market": "market",
            "policy": "policy",
        },
    )

    # All specialist agents → validation
    for agent_node in ["risk", "planner", "market", "policy"]:
        workflow.add_edge(agent_node, "validation")

    # After validation: retry → intent (with incremented counter), pass → explanation
    workflow.add_conditional_edges(
        "validation",
        should_retry,
        {"retry": "intent", "pass": "explanation"},
    )

    # Explanation → END
    workflow.add_edge("explanation", END)

    # ── Compile with Redis checkpointer ───────────────────────────────────────
    checkpointer = get_checkpointer()
    graph = workflow.compile(checkpointer=checkpointer)
    logger.info("LangGraph agent graph compiled successfully")
    return graph


# Module-level singleton — imported by API layer
_graph = None


def get_graph():
    global _graph
    if _graph is None:
        _graph = build_graph()
    return _graph
