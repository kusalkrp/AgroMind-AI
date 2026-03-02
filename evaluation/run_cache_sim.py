"""
CAG Cache Simulation — simulates 100 queries with Zipf distribution to measure
cache hit rate, latency speedup, and estimated API cost savings.

Usage:
    python evaluation/run_cache_sim.py
    python evaluation/run_cache_sim.py --queries 200 --unique 30
"""
from __future__ import annotations

import argparse
import asyncio
import json
import time
from pathlib import Path

import numpy as np
from loguru import logger

from knowledge.cag import cache_response, flush_all_cache, get_cache_stats, get_cached_response

RESULTS_PATH = Path("evaluation/results/cag_simulation.json")

# Realistic Sri Lankan agricultural query pool
QUERY_POOL = [
    "Is it safe to plant paddy in Anuradhapura this month?",
    "What is the disease risk for tomatoes in Kandy?",
    "When is the best time to sell paddy?",
    "What fertilizer should I use for rice in Maha season?",
    "How much nitrogen is safe for paddy per hectare?",
    "What are the signs of Brown Plant Hopper in rice?",
    "What is the current market price for tomatoes?",
    "Are there any government subsidies for coconut farmers?",
    "What varieties of paddy are suitable for dry zone?",
    "How do I control blast disease in paddy?",
    "What is the weather forecast risk for Jaffna farmers?",
    "When should I plant tomatoes in the Upcountry?",
    "What is the recommended pH for paddy cultivation?",
    "How can I improve soil organic matter in Kurunegala?",
    "What are the irrigation requirements for coconut?",
    "Is there a subsidy for fertilizer in 2024?",
    "What is the best rubber variety for Wet Zone?",
    "How do I manage Phytophthora in rubber?",
    "What is the price of coconut at Colombo market?",
    "What crops are suitable for Hambantota district?",
    "How do I apply for crop insurance?",
    "What is the recommended spacing for tomato plants?",
    "What are the signs of root wilt in coconut?",
    "When is the Yala paddy planting season?",
    "What is the expected yield for BG 360 variety?",
]

SIMULATED_PIPELINE_LATENCY_MS = 800  # realistic LLM + retrieval latency
GEMINI_COST_PER_CALL_USD = 0.00158   # approximate gemini-1.5-flash cost


async def simulate_queries(
    total_queries: int = 100,
    unique_queries: int = 25,
) -> dict:
    """
    Simulate query traffic with Zipf distribution (some queries repeat heavily).

    Args:
        total_queries: Total number of queries to simulate.
        unique_queries: Number of unique query types in the pool.

    Returns:
        Simulation report dict.
    """
    # Flush existing cache for clean simulation
    flush_all_cache()

    pool = QUERY_POOL[:min(unique_queries, len(QUERY_POOL))]

    # Zipf distribution: first queries repeat much more often (seasonal patterns)
    zipf_weights = np.array([1.0 / i for i in range(1, len(pool) + 1)])
    zipf_weights /= zipf_weights.sum()

    selected_queries = np.random.choice(pool, size=total_queries, p=zipf_weights)

    hit_latencies_ms: list[float] = []
    miss_latencies_ms: list[float] = []

    for i, query in enumerate(selected_queries):
        start = time.perf_counter()
        cached = get_cached_response(query)
        elapsed_ms = (time.perf_counter() - start) * 1000

        if cached:
            hit_latencies_ms.append(elapsed_ms)
        else:
            # Simulate full pipeline (LLM + retrieval)
            await asyncio.sleep(SIMULATED_PIPELINE_LATENCY_MS / 1000)
            miss_latencies_ms.append(SIMULATED_PIPELINE_LATENCY_MS)

            # Cache the result for next occurrence
            cache_response(
                query=query,
                response={
                    "answer": f"[Simulated answer for: {query[:60]}]",
                    "confidence": 0.82,
                },
            )

        if (i + 1) % 20 == 0:
            stats = get_cache_stats()
            logger.info(
                f"Progress {i+1}/{total_queries} — "
                f"hit_rate={stats['hit_rate']:.1%}"
            )

    stats = get_cache_stats()
    avg_hit_ms = round(sum(hit_latencies_ms) / max(len(hit_latencies_ms), 1), 2)
    avg_miss_ms = SIMULATED_PIPELINE_LATENCY_MS
    speedup = round(avg_miss_ms / max(avg_hit_ms, 0.1), 1)
    cost_saved = round(stats["hit_count"] * GEMINI_COST_PER_CALL_USD, 4)

    report = {
        "simulation_config": {
            "total_queries": total_queries,
            "unique_query_types": len(pool),
            "distribution": "zipf",
            "pipeline_latency_ms": SIMULATED_PIPELINE_LATENCY_MS,
        },
        "results": {
            "cache_hits": stats["hit_count"],
            "cache_misses": stats["miss_count"],
            "hit_rate_pct": round(stats["hit_rate"] * 100, 1),
            "avg_hit_latency_ms": avg_hit_ms,
            "avg_miss_latency_ms": avg_miss_ms,
            "speedup_factor": speedup,
            "estimated_api_calls_saved": stats["hit_count"],
            "estimated_cost_saved_usd": cost_saved,
        },
    }

    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(RESULTS_PATH, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    logger.info(
        f"Cache simulation complete:\n"
        f"  Hit rate: {report['results']['hit_rate_pct']}%\n"
        f"  Speedup: {speedup}x\n"
        f"  Cost saved: ${cost_saved}"
    )
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run CAG cache simulation")
    parser.add_argument("--queries", type=int, default=100)
    parser.add_argument("--unique", type=int, default=25)
    args = parser.parse_args()

    report = asyncio.run(simulate_queries(args.queries, args.unique))
    print(json.dumps(report, indent=2))
