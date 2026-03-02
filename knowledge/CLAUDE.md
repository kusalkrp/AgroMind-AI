# CLAUDE.md — knowledge/

This file provides guidance to Claude Code (claude.ai/code) when working in this directory.

## RAG Pipeline Order

Every query passes through these steps in order. Do not skip or reorder:

```
1. CAG check       (knowledge/cag.py)                  → cache HIT: return immediately
2. Hybrid retrieval (knowledge/retrievers/semantic_retriever.py) → top 15 chunks
3. Cross-encoder rerank (knowledge/reranker.py)         → top 5 chunks
4. CRAG grading    (knowledge/crag.py)                  → filter by score ≥ 0.5
5. Web fallback    (if all chunks score < 0.5)          → set state["needs_web_fallback"] = True
```

All retrieval is triggered from `agents/intent_agent.py`. Nothing in `knowledge/` should import from `agents/`.

## Retriever Contract

Every retriever returns `List[str]` of chunk text strings — no wrapper objects.

```python
def retrieve(query: str, **kwargs) -> List[str]:
    ...
    return [point.payload["text"] for point in results]
```

| Retriever | File | Data source | Key kwargs |
|---|---|---|---|
| Semantic | `retrievers/semantic_retriever.py` | Qdrant | `filters: dict`, `top_k: int` |
| Temporal | `retrievers/temporal_retriever.py` | TimescaleDB | `district: str`, `days_lookback: int` |
| Geo | `retrievers/geo_retriever.py` | PostgreSQL+PostGIS | `district: str` |

## Qdrant Collection

Collection name: `agromind_knowledge` (defined in `config/settings.py` as `QDRANT_COLLECTION`)

- Dense vector: `"dense"`, 768-dim, cosine distance (Gemini `text-embedding-004`)
- Sparse vector: `"sparse"`, BM25 (Qdrant sparse index, `on_disk=False`)
- Fusion: RRF with `rank_constant=60`
- Metadata fields on each point: `text`, `crop_types` (list), `districts` (list), `document_type`, `source_url`, `page_number`

Never call `recreate_collection` outside of initial setup scripts — it wipes all data.

## CRAG — Chunk Grading

```
Grades:    relevant | partial | irrelevant
Threshold: score ≥ 0.5 → kept
           score < 0.5 for ALL chunks → set needs_web_fallback = True
```

- Truncate chunk to 500 chars before sending to Gemini grader (cost control)
- On Gemini parse failure: default to `ChunkRelevance.PARTIAL`, score `0.5`
- `grade_chunks()` returns `List[GradedChunk]`
- `filter_relevant_chunks()` returns `(List[str] | None, bool)` — chunks and fallback flag

## CAG — Cache Layer

- Key format: `cag:{sha256(query.lower().strip() + ":" + context_hash)}`
- TTL: 24 hours
- Hit increments `cag:hit_count` counter in Redis; miss increments `cag:miss_count`
- `get_cache_stats()` returns hit_rate, useful for evaluation reports
- Cache is written by `explanation_agent.py` after final answer is generated — not here

## Reranker

Model: `cross-encoder/ms-marco-MiniLM-L-6-v2` (loaded once at module level, not per-call)

```python
model = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")  # module-level singleton
```

Input: `(query: str, chunks: List[str], top_k: int = 5)`
Output: `List[tuple[str, float]]` sorted by score descending

## Embeddings

Primary: `genai.embed_content(model="models/text-embedding-004", content=text)` → 768-dim
Fallback: `sentence-transformers/paraphrase-multilingual-mpnet-base-v2` — use when Gemini is unavailable or for Sinhala/Tamil content

Always use the primary embedder for Qdrant ingestion so query and document vectors are in the same space.
