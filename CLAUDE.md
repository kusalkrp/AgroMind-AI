# CLAUDE.md — AgroMind AI

## Project Overview
Agentic RAG system for Sri Lankan agricultural intelligence.
Multi-agent LangGraph DAG with hybrid RAG (Qdrant + TimescaleDB + PostGIS).
Only paid service: Google Gemini API (LLM + embeddings).

## Stack
- Python 3.11, FastAPI, LangGraph, LlamaIndex
- Qdrant (vector), TimescaleDB (temporal), PostgreSQL+PostGIS (geo), Redis (cache)
- Google Gemini 1.5 Flash (LLM), text-embedding-004 (embeddings)
- Evaluation: RAGAS, MLflow, LangSmith

## Commands
- Start stack:     docker-compose up -d
- Run API:         uvicorn api.main:app --reload
- Run tests:       pytest tests/ -v
- Run ingestion:   celery -A ingestion.pipeline worker
- Run RAGAS eval:  python evaluation/run_ragas.py
- Run CAG sim:     python evaluation/run_cache_sim.py

## Code Conventions
- All agents follow the same pattern: function_name(state: AgentState) -> AgentState
- All retrievers return List[str] of chunk texts
- Use Pydantic for ALL data models — no raw dicts in API layer
- Use Loguru for logging: from loguru import logger
- Every agent must append to state["reasoning_trace"]
- Config via pydantic-settings from .env — never hardcode credentials

## Architecture Rules
- Agents NEVER call retrievers directly — always through orchestration/agent_graph.py
- CRAG grading happens in intent_node before any specialist agent runs
- CAG cache check is always the FIRST node in the LangGraph DAG
- Validation agent uses crops.yaml rules — NOT LLM judgment for hard limits

## Key File References
- Agent pattern example:    agents/intent_agent.py
- State definition:         orchestration/state.py
- Retriever pattern:        knowledge/retrievers/semantic_retriever.py
- Test pattern:             tests/unit/test_risk_agent.py

## Testing Rules
- Every new agent needs a corresponding test in tests/unit/
- Every retriever needs an integration test in tests/integration/
- Run pytest before every commit