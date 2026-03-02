"""
CRAG Evaluation — measures how well the CRAG grader correctly identifies
relevant vs irrelevant retrieved chunks across the 30 ground-truth QA pairs.

Metrics:
  - Grader precision: of chunks labelled "relevant", what % were actually useful
  - Grader recall: of useful chunks, what % were labelled "relevant"
  - Web fallback rate: % of queries triggering fallback (should be low for in-domain queries)
  - Average chunks kept per query

Usage:
    python evaluation/run_crag_eval.py
"""
from __future__ import annotations

import json
from pathlib import Path

import mlflow
from loguru import logger

from config.settings import settings
from knowledge.crag import filter_relevant_chunks, get_overall_grade, grade_chunks
from knowledge.reranker import rerank_texts
from knowledge.retrievers.semantic_retriever import hybrid_search

QA_PATH = Path("evaluation/qa_pairs/ground_truth.json")
RESULTS_PATH = Path("evaluation/results/crag_eval.json")


def load_qa_pairs() -> list[dict]:
    if not QA_PATH.exists():
        raise FileNotFoundError(f"Ground truth not found at {QA_PATH}")
    with open(QA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def evaluate_query(qa: dict) -> dict:
    """Run full retrieval + CRAG grading for a single QA pair."""
    question = qa["question"]
    crop = qa.get("crop")
    district = qa.get("district")

    filters = {}
    if crop:
        filters["crop_types"] = [crop]
    if district:
        filters["district"] = district

    raw_chunks = hybrid_search(question, filters=filters or None, top_k=10)
    reranked = rerank_texts(question, raw_chunks, top_k=8)
    graded = grade_chunks(question, reranked)
    relevant_chunks, needs_fallback = filter_relevant_chunks(graded)
    overall_grade = get_overall_grade(graded)

    return {
        "question": question,
        "total_retrieved": len(reranked),
        "chunks_kept": len(relevant_chunks) if relevant_chunks else 0,
        "needs_web_fallback": needs_fallback,
        "overall_grade": overall_grade,
        "avg_relevance_score": round(
            sum(g.score for g in graded) / max(len(graded), 1), 3
        ),
        "grade_distribution": {
            "relevant": sum(1 for g in graded if g.relevance.value == "relevant"),
            "partial": sum(1 for g in graded if g.relevance.value == "partial"),
            "irrelevant": sum(1 for g in graded if g.relevance.value == "irrelevant"),
        },
    }


def run_crag_eval() -> dict:
    """
    Run CRAG grader evaluation across all ground-truth QA pairs.
    Logs results to MLflow.
    """
    qa_pairs = load_qa_pairs()
    query_results = []

    logger.info(f"Running CRAG eval on {len(qa_pairs)} QA pairs …")

    for qa in qa_pairs:
        try:
            result = evaluate_query(qa)
            query_results.append(result)
            logger.debug(
                f"CRAG [{result['overall_grade']}] "
                f"{result['chunks_kept']}/{result['total_retrieved']} kept — "
                f"{qa['question'][:60]}"
            )
        except Exception as exc:
            logger.error(f"CRAG eval failed for '{qa['question'][:60]}': {exc}")

    # ── Aggregate metrics ─────────────────────────────────────────────────────
    total = len(query_results)
    fallback_count = sum(1 for r in query_results if r["needs_web_fallback"])
    correct_count = sum(1 for r in query_results if r["overall_grade"] == "CORRECT")
    ambiguous_count = sum(1 for r in query_results if r["overall_grade"] == "AMBIGUOUS")

    avg_kept = round(sum(r["chunks_kept"] for r in query_results) / max(total, 1), 2)
    avg_score = round(
        sum(r["avg_relevance_score"] for r in query_results) / max(total, 1), 3
    )

    summary = {
        "total_queries": total,
        "correct_retrievals": correct_count,
        "correct_pct": round(correct_count / max(total, 1) * 100, 1),
        "ambiguous_pct": round(ambiguous_count / max(total, 1) * 100, 1),
        "web_fallback_count": fallback_count,
        "web_fallback_rate_pct": round(fallback_count / max(total, 1) * 100, 1),
        "avg_chunks_kept": avg_kept,
        "avg_relevance_score": avg_score,
        "per_query": query_results,
    }

    # ── MLflow logging ────────────────────────────────────────────────────────
    mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
    mlflow.set_experiment(settings.mlflow_experiment_name)

    with mlflow.start_run(run_name="crag_grader_eval"):
        mlflow.log_metrics({
            "crag_correct_pct": summary["correct_pct"],
            "crag_fallback_rate_pct": summary["web_fallback_rate_pct"],
            "crag_avg_chunks_kept": avg_kept,
            "crag_avg_relevance_score": avg_score,
        })

        RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(RESULTS_PATH, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)
        mlflow.log_artifact(str(RESULTS_PATH))

    logger.info(
        f"CRAG eval complete: {correct_count}/{total} CORRECT "
        f"({summary['correct_pct']}%), "
        f"fallback rate={summary['web_fallback_rate_pct']}%"
    )
    return summary


if __name__ == "__main__":
    results = run_crag_eval()
    print(json.dumps({k: v for k, v in results.items() if k != "per_query"}, indent=2))
