# CLAUDE.md — evaluation/

This file provides guidance to Claude Code (claude.ai/code) when working in this directory.

## What Gets Evaluated

| Script | What it tests | Output |
|---|---|---|
| `run_ragas.py` | 5 chunking strategies via RAGAS metrics | `results/chunking_eval.json` |
| `run_crag_eval.py` | CRAG grader accuracy vs manual labels | `results/crag_eval.json` |
| `run_cache_sim.py` | CAG hit rate over 100 queries (Zipf distribution) | `results/cag_simulation.json` |

## Ground Truth (`qa_pairs/ground_truth.json`)

30 hand-verified QA pairs. Format:

```json
[
  {
    "question": "What is the disease risk for paddy in Anuradhapura during Maha season?",
    "answer": "...",
    "context_doc": "doa_paddy_guide_2023.pdf",
    "intent": "disease",
    "district": "anuradhapura",
    "crop": "paddy"
  }
]
```

Cover all 4 intents (disease, planning, market, policy) and at least 5 districts. Do not generate QA pairs with an LLM — all 30 must be manually written and verified against source documents.

## RAGAS Metrics

Three metrics evaluated per chunking strategy:

| Metric | Meaning | Target |
|---|---|---|
| `faithfulness` | Answer supported by retrieved context | > 0.95 |
| `answer_relevancy` | Answer addresses the question | > 0.90 |
| `context_recall` | Ground truth covered by retrieved chunks | > 0.85 |

Run with MLflow tracking:

```python
with mlflow.start_run(run_name="chunking_strategy_eval"):
    mlflow.log_metrics({f"{strategy}_faithfulness": score, ...})
```

MLflow server: `http://localhost:5000` (set `MLFLOW_TRACKING_URI` in `.env`)

## CAG Simulation Parameters

- 100 queries drawn from `QUERY_POOL` with **Zipf distribution** (not uniform) to model seasonal repeat patterns
- Simulated miss latency: 500ms (represents full Gemini + retrieval pipeline)
- Report keys: `hit_rate_pct`, `avg_hit_latency_ms`, `speedup_factor`, `estimated_cost_saved_usd`
- Target: hit rate > 70%, speedup > 15x

Cost formula: `hits * 0.00158` USD (Gemini 1.5 Flash pricing per query as of implementation)

## CRAG Evaluation

Compare Gemini's chunk grades vs manual labels on 20 query categories.
- Manual labels: `relevant`, `partial`, `irrelevant` per chunk
- Accuracy = exact match between Gemini grade and manual label
- Target: > 85% accuracy
- Store per-category breakdown (disease queries vs market queries vs policy queries)

## Adding New Evaluation Scripts

- Output always goes to `evaluation/results/` as JSON
- Always log to MLflow with a meaningful `run_name`
- Print a brief summary to stdout (hit rate %, top score, etc.) so CI can capture it
- Scripts are standalone — import from `knowledge/` and `agents/` but never modify state
