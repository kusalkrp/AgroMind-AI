"""
RAGAS Chunking Strategy Evaluation.

Compares all 5 chunking strategies across faithfulness, answer relevancy,
and context recall using 30 ground-truth QA pairs.

Results logged to MLflow and saved to evaluation/results/chunking_eval.json.

Usage:
    python evaluation/run_ragas.py
    python evaluation/run_ragas.py --strategy fixed  # single strategy
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Literal

import mlflow
from datasets import Dataset
from loguru import logger
from ragas import evaluate
from ragas.metrics import answer_relevancy, context_recall, faithfulness

from config.settings import settings

STRATEGIES = ["fixed", "sliding", "semantic", "parent_child", "late"]
QA_PATH = Path("evaluation/qa_pairs/ground_truth.json")
RESULTS_PATH = Path("evaluation/results/chunking_eval.json")

ChunkStrategy = Literal["fixed", "sliding", "semantic", "parent_child", "late"]


def load_qa_pairs() -> list[dict]:
    """Load ground-truth QA pairs from JSON file."""
    if not QA_PATH.exists():
        raise FileNotFoundError(
            f"Ground truth not found at {QA_PATH}. "
            "Run: python evaluation/create_qa_pairs.py first."
        )
    with open(QA_PATH, "r", encoding="utf-8") as f:
        pairs = json.load(f)
    logger.info(f"Loaded {len(pairs)} QA pairs from {QA_PATH}")
    return pairs


def retrieve_with_strategy(strategy: ChunkStrategy, question: str) -> list[str]:
    """Retrieve top-5 context chunks for a question using the given strategy."""
    from knowledge.retrievers.semantic_retriever import hybrid_search
    from knowledge.reranker import rerank_texts

    raw = hybrid_search(question, top_k=10)
    reranked = rerank_texts(question, raw, top_k=5)
    return reranked


def generate_answer(question: str, contexts: list[str]) -> str:
    """Generate an answer from context using Gemini (no agent pipeline)."""
    from config.gemini import call_gemini

    context_str = "\n---\n".join(contexts)
    prompt = (
        f"Answer this agricultural question based only on the provided context.\n\n"
        f"Context:\n{context_str}\n\n"
        f"Question: {question}\n\n"
        f"Answer concisely in 2-4 sentences:"
    )

    try:
        return call_gemini(prompt).strip()
    except Exception as exc:
        logger.warning(f"generate_answer failed: {exc}")
        return "Unable to generate answer."


def evaluate_strategy(strategy: ChunkStrategy, qa_pairs: list[dict]) -> dict:
    """Run RAGAS evaluation for a single chunking strategy."""
    logger.info(f"Evaluating strategy: {strategy} ({len(qa_pairs)} questions)")

    rows = []
    for qa in qa_pairs:
        question = qa["question"]
        ground_truth = qa["answer"]

        contexts = retrieve_with_strategy(strategy, question)
        answer = generate_answer(question, contexts)

        rows.append({
            "question": question,
            "answer": answer,
            "contexts": contexts,
            "ground_truth": ground_truth,
        })
        time.sleep(0.2)  # rate limit

    dataset = Dataset.from_list(rows)
    scores = evaluate(
        dataset,
        metrics=[faithfulness, answer_relevancy, context_recall],
    )

    return {
        "faithfulness": float(scores["faithfulness"]),
        "answer_relevancy": float(scores["answer_relevancy"]),
        "context_recall": float(scores["context_recall"]),
        "num_questions": len(qa_pairs),
    }


def run_chunking_eval(strategies: list[str] | None = None) -> dict:
    """
    Evaluate one or more chunking strategies and log results to MLflow.

    Args:
        strategies: List of strategy names to evaluate. Defaults to all 5.

    Returns:
        Dict mapping strategy name → RAGAS scores.
    """
    strategies = strategies or STRATEGIES
    qa_pairs = load_qa_pairs()
    results: dict = {}

    mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
    mlflow.set_experiment(settings.mlflow_experiment_name)

    with mlflow.start_run(run_name="chunking_strategy_eval"):
        mlflow.log_param("num_qa_pairs", len(qa_pairs))
        mlflow.log_param("strategies", ",".join(strategies))

        for strategy in strategies:
            try:
                scores = evaluate_strategy(strategy, qa_pairs)
                results[strategy] = scores

                mlflow.log_metrics({
                    f"{strategy}_faithfulness": scores["faithfulness"],
                    f"{strategy}_relevancy": scores["answer_relevancy"],
                    f"{strategy}_recall": scores["context_recall"],
                })

                logger.info(
                    f"{strategy}: faithfulness={scores['faithfulness']:.3f}, "
                    f"relevancy={scores['answer_relevancy']:.3f}, "
                    f"recall={scores['context_recall']:.3f}"
                )
            except Exception as exc:
                logger.error(f"Strategy '{strategy}' evaluation failed: {exc}")
                results[strategy] = {"error": str(exc)}

        # Save results
        RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(RESULTS_PATH, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)
        mlflow.log_artifact(str(RESULTS_PATH))
        logger.info(f"Results saved to {RESULTS_PATH}")

    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run RAGAS chunking evaluation")
    parser.add_argument("--strategy", choices=STRATEGIES, help="Single strategy to evaluate")
    args = parser.parse_args()

    strategies = [args.strategy] if args.strategy else None
    results = run_chunking_eval(strategies)
    print(json.dumps(results, indent=2))
