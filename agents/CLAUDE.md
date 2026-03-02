# CLAUDE.md — agents/

This file provides guidance to Claude Code (claude.ai/code) when working in this directory.

## Agent Contract

Every agent is a single function with this exact signature:

```python
def <name>_node(state: AgentState) -> AgentState:
    ...
    state["reasoning_trace"].append("AgentName: one-line summary")
    return state
```

- Import `AgentState` from `orchestration/state.py`
- Mutate state in place — never construct a new dict or return a partial state
- Always append to `state["reasoning_trace"]` before returning
- Log with `from loguru import logger`, not `print` or `logging`

## Agents and Their State Contracts

| Agent | File | Reads from state | Writes to state |
|---|---|---|---|
| intent | `intent_agent.py` | `query`, `district`, `crop` | `intent`, `sub_tasks`, `semantic_context`, `chunk_grades`, `needs_web_fallback` |
| risk | `risk_agent.py` | `crop`, `district`, `semantic_context` | `risk_assessment`, `risk_level` |
| planner | `planner_agent.py` | `crop`, `district`, `semantic_context` | `planner_recommendation` |
| market | `market_agent.py` | `crop`, `district` | `market_insight` |
| policy | `policy_agent.py` | `crop`, `district`, `semantic_context` | `policy_matches` |
| validation | `validation_agent.py` | `crop`, `planner_recommendation`, `citations` | `validation_violations`, `validation_passed`, `confidence_score` |
| explanation | `explanation_agent.py` | `language`, `query`, `risk_assessment`, `planner_recommendation`, `confidence_score` | `final_answer` + caches result |

## Gemini Call Pattern

All agents call Gemini and expect strict JSON back. Use this pattern consistently:

```python
import google.generativeai as genai
import json
from loguru import logger

model = genai.GenerativeModel("gemini-2.5-flash")

def _call_gemini(prompt: str, fallback: dict) -> dict:
    try:
        response = model.generate_content(prompt)
        return json.loads(response.text.strip())
    except Exception as e:
        logger.warning(f"Gemini call failed: {e}")
        return fallback
```

- Prompts must say **"Return ONLY valid JSON"** with the exact schema shown
- Always provide a `fallback` dict for when parsing fails — never let an agent crash the graph
- Truncate chunk text to 500 chars when passing to Gemini graders

## Retrieval Rule

Agents **never** call retrievers directly. Retrieval happens exclusively in `intent_node` (via `orchestration/agent_graph.py`). Specialist agents (risk, planner, market, policy) only read `state["semantic_context"]` which is already populated.

The one exception: `risk_agent.py` may call `knowledge/retrievers/temporal_retriever.py` directly for weather data because it is time-sensitive and not part of semantic context.

## Adding a New Agent

1. Create `agents/<name>_agent.py` with `<name>_node(state) -> AgentState`
2. Add the node to `orchestration/agent_graph.py` (`workflow.add_node(...)`)
3. Wire edges in `orchestration/edges.py`
4. Add the output key to `AgentState` in `orchestration/state.py`
5. Write `tests/unit/test_<name>_agent.py` — mock Gemini with `unittest.mock.patch`
