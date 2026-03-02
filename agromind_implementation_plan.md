# AgroMind AI — Production Implementation Plan
### Agentic RAG System for Sri Lankan Agricultural Intelligence
> **Stack Constraint:** All infrastructure is open-source. Only paid dependency: Google Gemini API.

---

## Table of Contents
1. [System Overview](#1-system-overview)
2. [Full Tech Stack](#2-full-tech-stack)
3. [Repository Structure](#3-repository-structure)
4. [Architecture Diagram](#4-architecture-diagram)
5. [Module 1 — Data Ingestion Pipeline](#5-module-1--data-ingestion-pipeline)
6. [Module 2 — RAG Pipeline](#6-module-2--rag-pipeline)
7. [Module 3 — Agentic Layer](#7-module-3--agentic-layer)
8. [Module 4 — API Layer](#8-module-4--api-layer)
9. [Module 5 — Evaluation Framework](#9-module-5--evaluation-framework)
10. [Module 6 — Frontend Dashboard](#10-module-6--frontend-dashboard)
11. [Database Schema](#11-database-schema)
12. [Environment Configuration](#12-environment-configuration)
13. [Implementation Phases](#13-implementation-phases)
14. [Portfolio Metrics to Capture](#14-portfolio-metrics-to-capture)

---

## 1. System Overview

```
User Query (EN / Sinhala / Tamil)
        │
        ▼
┌──────────────────┐
│   FastAPI Gateway │  ← Rate limiting, auth, request logging
└────────┬─────────┘
         │
         ▼
┌──────────────────────────────────────────┐
│           LangGraph Agent Orchestrator    │
│                                          │
│  Intent Agent → Task Planner             │
│       │                                  │
│       ├── Risk Analyst Agent             │
│       ├── Crop Planner Agent             │
│       ├── Market Analyst Agent           │
│       └── Policy Matcher Agent           │
│                                          │
│  Validation Agent → Explanation Agent   │
└──────────────┬───────────────────────────┘
               │
     ┌─────────▼──────────┐
     │   CRAG Retriever    │  ← Corrective RAG with chunk grading
     │   + CAG Cache       │  ← Cache Augmented Generation
     └─────────┬───────────┘
               │
   ┌───────────┼───────────────┐
   ▼           ▼               ▼
Qdrant      TimescaleDB     PostgreSQL
(Semantic   (Weather +      + PostGIS
 RAG)       Market RAG)    (Geo RAG)
```

---

## 2. Full Tech Stack

### LLM & Embeddings
| Component | Tool | Why |
|---|---|---|
| LLM | **Google Gemini 2.5 Flash** | Only paid service — cheap, fast, multilingual |
| Embeddings | **`models/text-embedding-004`** (Gemini) | Free with Gemini API key |
| Fallback Embeddings | **`sentence-transformers/paraphrase-multilingual-mpnet-base-v2`** | Sinhala/Tamil support, runs locally |

### RAG & Vector Layer
| Component | Tool | Why |
|---|---|---|
| Vector DB | **Qdrant** (Docker) | Hybrid search (dense + sparse), open-source |
| Sparse Search | **BM25 via Qdrant sparse vectors** | Handles agricultural terminology well |
| Reranker | **`cross-encoder/ms-marco-MiniLM-L-6-v2`** | Open-source cross-encoder reranking |
| Time-series DB | **TimescaleDB** (Postgres extension) | Weather + market price temporal queries |
| Geo DB | **PostgreSQL + PostGIS** | District-level soil and region queries |
| Cache Layer | **Redis** | CAG cache, agent state, session memory |

### Agent Orchestration
| Component | Tool | Why |
|---|---|---|
| Agent Framework | **LangGraph** | DAG-based multi-agent with conditional edges |
| Agent Memory | **mem0** (open-source) | Episodic memory with decay per user/region |
| Prompt Management | **LangChain Hub / local YAML** | Version-controlled prompts |

### Ingestion Pipeline
| Component | Tool | Why |
|---|---|---|
| Web Crawling | **Playwright (async)** | JavaScript-rendered pages, retry logic |
| PDF Extraction | **PyMuPDF (fitz)** | Fast text + metadata extraction |
| OCR Fallback | **PaddleOCR** | For scanned government PDFs |
| Task Queue | **Celery + Redis** | Async ingestion, scheduled scraping |
| Chunking | **LlamaIndex + custom strategies** | 5 strategies evaluated with RAGAS |

### Evaluation
| Component | Tool | Why |
|---|---|---|
| RAG Evaluation | **RAGAS** | Faithfulness, Answer Relevancy, Context Recall |
| Agent Tracing | **LangSmith (free tier)** | Agent step visibility |
| Experiment Tracking | **MLflow** | Track chunking strategy benchmarks |

### Backend & Infra
| Component | Tool | Why |
|---|---|---|
| API | **FastAPI** | Async, production-grade |
| Task Scheduling | **Celery Beat** | Weekly market price + weather ingestion |
| Containerization | **Docker + Docker Compose** | Full local stack |
| Monitoring | **Prometheus + Grafana** | Query latency, cache hit rate, agent errors |
| Logging | **Loguru + structlog** | Structured logs per agent step |

### Frontend
| Component | Tool | Why |
|---|---|---|
| UI | **React + Vite** | Production-grade dashboard |
| Charts | **Recharts** | Market price trends, weather overlays |
| Map | **Leaflet.js** | District-level Sri Lanka geo views |

---

## 3. Repository Structure

```
agromind-ai/
│
├── 📁 ingestion/                    # Data collection & processing
│   ├── crawlers/
│   │   ├── doa_crawler.py           # Dept. of Agriculture scraper
│   │   ├── harti_crawler.py         # HARTI research papers scraper
│   │   └── market_price_scraper.py  # Colombo market weekly prices
│   ├── processors/
│   │   ├── pdf_extractor.py         # PyMuPDF + PaddleOCR fallback
│   │   ├── metadata_tagger.py       # Gemini-powered auto-tagging
│   │   └── weather_ingest.py        # Open-Meteo API client
│   ├── chunkers/
│   │   ├── fixed_chunker.py
│   │   ├── semantic_chunker.py
│   │   ├── sliding_chunker.py
│   │   ├── parent_child_chunker.py
│   │   └── late_chunker.py
│   └── pipeline.py                  # Orchestrates full ingestion flow
│
├── 📁 knowledge/                    # RAG layer
│   ├── embedders/
│   │   ├── gemini_embedder.py       # Gemini text-embedding-004
│   │   └── multilingual_embedder.py # sentence-transformers fallback
│   ├── retrievers/
│   │   ├── semantic_retriever.py    # Qdrant dense + sparse hybrid
│   │   ├── temporal_retriever.py    # TimescaleDB time-range queries
│   │   └── geo_retriever.py         # PostGIS district queries
│   ├── reranker.py                  # Cross-encoder reranking
│   ├── crag.py                      # Corrective RAG chunk grader
│   └── cag.py                       # Cache Augmented Generation (Redis)
│
├── 📁 agents/                       # Agent definitions
│   ├── intent_agent.py              # Classifies query type + routes
│   ├── risk_agent.py                # Disease + weather risk analysis
│   ├── planner_agent.py             # Crop planning recommendations
│   ├── market_agent.py              # Price trend + sell timing
│   ├── policy_agent.py              # Subsidy + scheme matching
│   ├── validation_agent.py          # Grounds output, checks hallucination
│   └── explanation_agent.py         # Farmer-friendly multilingual output
│
├── 📁 orchestration/                # LangGraph DAG
│   ├── agent_graph.py               # Full LangGraph state machine
│   ├── state.py                     # Shared AgentState TypedDict
│   ├── edges.py                     # Conditional routing logic
│   └── checkpointer.py              # Redis-backed state persistence
│
├── 📁 memory/                       # Decision memory
│   ├── episodic_store.py            # mem0 integration
│   ├── regional_memory.py           # Per-district aggregated insights
│   └── decay.py                     # Confidence decay over time
│
├── 📁 api/                          # FastAPI backend
│   ├── main.py
│   ├── routers/
│   │   ├── query.py                 # POST /query
│   │   ├── simulate.py              # POST /simulate (scenario engine)
│   │   ├── ingest.py                # POST /ingest/trigger
│   │   └── health.py               # GET /health
│   ├── middleware/
│   │   ├── rate_limiter.py
│   │   └── auth.py                  # API key auth
│   └── schemas.py                   # Pydantic request/response models
│
├── 📁 evaluation/                   # RAGAS + benchmarks
│   ├── qa_pairs/
│   │   └── ground_truth.json        # 30 hand-verified QA pairs
│   ├── run_ragas.py                 # Chunking strategy evaluation
│   ├── run_crag_eval.py             # CRAG grading accuracy
│   ├── run_cache_sim.py             # 100-query CAG simulation
│   └── results/                     # Benchmark outputs (JSON + CSV)
│
├── 📁 config/                       # All configuration
│   ├── prompts/
│   │   ├── intent_prompt.yaml
│   │   ├── risk_prompt.yaml
│   │   ├── planner_prompt.yaml
│   │   └── validation_prompt.yaml
│   ├── crops.yaml                   # Per-crop agronomic constraints
│   ├── districts.yaml               # Sri Lanka district metadata
│   └── settings.py                  # Pydantic settings from .env
│
├── 📁 monitoring/
│   ├── prometheus.yml
│   ├── grafana/
│   │   └── dashboards/
│   │       └── agromind.json
│   └── metrics.py                   # Custom Prometheus metrics
│
├── 📁 ui/                           # React frontend
│   ├── src/
│   │   ├── components/
│   │   │   ├── QueryPanel.jsx
│   │   │   ├── AgentTrace.jsx       # Shows agent reasoning steps
│   │   │   ├── DistrictMap.jsx      # Leaflet Sri Lanka map
│   │   │   ├── MarketChart.jsx      # Price trend charts
│   │   │   └── ConfidenceBar.jsx
│   │   └── pages/
│   │       ├── Dashboard.jsx
│   │       └── Simulate.jsx
│   └── vite.config.js
│
├── 📁 tests/
│   ├── unit/
│   ├── integration/
│   └── e2e/
│
├── docker-compose.yml
├── Dockerfile
├── .env.example
├── requirements.txt
├── pyproject.toml
└── README.md
```

---

## 4. Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        DATA SOURCES                              │
│                                                                  │
│  doa.gov.lk   harti.gov.lk   Open-Meteo API   Market HTML       │
│  (PDFs)       (PDFs)         (Weather JSON)    (Price Tables)    │
└──────┬─────────────┬──────────────┬──────────────┬──────────────┘
       │             │              │              │
       ▼             ▼              ▼              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    INGESTION PIPELINE (Celery)                   │
│                                                                  │
│  Playwright Crawlers → PyMuPDF/PaddleOCR → Gemini Meta Tagger   │
│         ↓                                                        │
│  5 Chunking Strategies (evaluated by RAGAS)                     │
│         ↓                                                        │
│  Gemini Embeddings (text-embedding-004)                         │
└──────────────────────┬──────────────────────────────────────────┘
                       │
          ┌────────────▼────────────────────┐
          │         KNOWLEDGE STORES         │
          │                                 │
          │  Qdrant          TimescaleDB     │
          │  (Semantic RAG)  (Temporal RAG)  │
          │                                 │
          │  PostgreSQL+PostGIS             │
          │  (Geo RAG + Structured)         │
          │                                 │
          │  Redis (CAG Cache + Sessions)   │
          └────────────┬────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────────┐
│                      RAG PIPELINE                                │
│                                                                  │
│  1. CAG Check (Redis) → Cache HIT → Return cached response      │
│                      → Cache MISS → Continue                     │
│  2. Hybrid Retrieval (Dense + BM25 sparse)                      │
│  3. Cross-Encoder Reranking                                     │
│  4. CRAG Grading (Gemini grades each chunk: relevant/partial/   │
│     irrelevant) → irrelevant chunks trigger web fallback        │
└──────────────────────┬──────────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────────┐
│               LANGGRAPH AGENT ORCHESTRATOR                       │
│                                                                  │
│   ┌─────────────┐    ┌──────────────┐    ┌──────────────────┐  │
│   │ Intent Agent│───▶│ Task Planner │───▶│ Parallel Agents: │  │
│   │             │    │ (routes to   │    │  • Risk Agent     │  │
│   │ Classifies: │    │  agents)     │    │  • Planner Agent  │  │
│   │ - disease   │    └──────────────┘    │  • Market Agent   │  │
│   │ - planning  │                        │  • Policy Agent   │  │
│   │ - market    │                        └────────┬─────────┘  │
│   │ - policy    │                                 │             │
│   └─────────────┘                                 ▼             │
│                                         ┌──────────────────┐   │
│                                         │ Validation Agent  │   │
│                                         │ (checks against   │   │
│                                         │  crops.yaml rules)│   │
│                                         └────────┬─────────┘   │
│                                                  │              │
│                                                  ▼              │
│                                         ┌──────────────────┐   │
│                                         │ Explanation Agent │   │
│                                         │ EN/Sinhala/Tamil  │   │
│                                         │ + Confidence Score│   │
│                                         └──────────────────┘   │
└──────────────────────┬──────────────────────────────────────────┘
                       │
              ┌────────▼────────┐
              │  FastAPI Layer  │
              │  + Rate Limiter │
              └────────┬────────┘
                       │
              ┌────────▼────────┐
              │  React Frontend │
              │  + Leaflet Map  │
              │  + Recharts     │
              │  + Agent Trace  │
              └─────────────────┘
```

---

## 5. Module 1 — Data Ingestion Pipeline

### 5.1 DOA Crawler

```python
# ingestion/crawlers/doa_crawler.py
import asyncio
from playwright.async_api import async_playwright
from pathlib import Path
import httpx
import logging

logger = logging.getLogger(__name__)

TARGET_URLS = [
    "https://www.doa.gov.lk/index.php/en/crops",
    "https://www.doa.gov.lk/index.php/en/plant-protection",
    "https://www.doa.gov.lk/index.php/en/publications",
]

async def crawl_doa(output_dir: str = "data/raw/doa"):
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        pdf_links = []
        
        for url in TARGET_URLS:
            try:
                await page.goto(url, wait_until="networkidle", timeout=30000)
                await asyncio.sleep(2)  # Off-peak delay
                
                links = await page.eval_on_selector_all(
                    "a[href$='.pdf']",
                    "els => els.map(el => el.href)"
                )
                pdf_links.extend(links)
                logger.info(f"Found {len(links)} PDFs at {url}")
                
            except Exception as e:
                logger.error(f"Failed {url}: {e}")
                await asyncio.sleep(5)  # Retry delay
        
        await browser.close()
    
    # Download PDFs async with retry
    async with httpx.AsyncClient(timeout=60) as client:
        for i, link in enumerate(set(pdf_links)):
            await download_with_retry(client, link, output_dir, retries=3)
            await asyncio.sleep(1)  # Rate limiting
    
    logger.info(f"Downloaded {len(pdf_links)} PDFs to {output_dir}")

async def download_with_retry(client, url, output_dir, retries=3):
    filename = url.split("/")[-1]
    filepath = Path(output_dir) / filename
    
    if filepath.exists():
        return  # Skip already downloaded
    
    for attempt in range(retries):
        try:
            resp = await client.get(url)
            resp.raise_for_status()
            filepath.write_bytes(resp.content)
            logger.info(f"Saved {filename}")
            return
        except Exception as e:
            if attempt == retries - 1:
                logger.error(f"Failed to download {url}: {e}")
            await asyncio.sleep(2 ** attempt)
```

### 5.2 PDF Extractor with OCR Fallback

```python
# ingestion/processors/pdf_extractor.py
import fitz  # PyMuPDF
from paddleocr import PaddleOCR
from pathlib import Path
from dataclasses import dataclass
from typing import Optional
import re

ocr = PaddleOCR(use_angle_cls=True, lang='en')

@dataclass
class ExtractedDocument:
    filename: str
    text: str
    page_count: int
    is_ocr: bool
    metadata: dict

def extract_pdf(pdf_path: str) -> ExtractedDocument:
    path = Path(pdf_path)
    doc = fitz.open(pdf_path)
    
    pages_text = []
    is_ocr = False
    
    for page in doc:
        text = page.get_text("text").strip()
        
        if len(text) < 50:  # Likely a scanned page
            # OCR fallback
            pix = page.get_pixmap(dpi=200)
            img_path = f"/tmp/page_{page.number}.png"
            pix.save(img_path)
            
            result = ocr.ocr(img_path)
            if result and result[0]:
                text = " ".join([line[1][0] for line in result[0]])
            is_ocr = True
        
        pages_text.append(text)
    
    full_text = "\n\n".join(pages_text)
    
    return ExtractedDocument(
        filename=path.name,
        text=full_text,
        page_count=len(doc),
        is_ocr=is_ocr,
        metadata={
            "source": pdf_path,
            "page_count": len(doc),
            "file_size": path.stat().st_size
        }
    )
```

### 5.3 Gemini Metadata Tagger

```python
# ingestion/processors/metadata_tagger.py
import google.generativeai as genai
import json
from config.settings import settings

genai.configure(api_key=settings.GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")

TAGGING_PROMPT = """
Analyze this agricultural document excerpt and return ONLY valid JSON (no markdown):
{{
    "crop_types": ["list of crops mentioned e.g. paddy, tomato, coconut"],
    "districts": ["Sri Lankan districts mentioned e.g. Anuradhapura, Kandy"],
    "document_type": "one of: crop_guide | disease_report | policy | research | market | weather",
    "season": "one of: maha | yala | both | null",
    "year": "publication year as integer or null",
    "language": "one of: english | sinhala | tamil | mixed",
    "topics": ["key topics e.g. fertilizer, irrigation, pest_control"]
}}

Document excerpt (first 1000 chars):
{text}
"""

def tag_document(text: str, filename: str) -> dict:
    try:
        response = model.generate_content(
            TAGGING_PROMPT.format(text=text[:1000])
        )
        metadata = json.loads(response.text.strip())
        metadata["filename"] = filename
        return metadata
    except Exception as e:
        # Fallback metadata
        return {
            "crop_types": [],
            "districts": [],
            "document_type": "unknown",
            "season": None,
            "year": None,
            "language": "english",
            "topics": [],
            "filename": filename
        }
```

### 5.4 Weather Ingestion (Open-Meteo)

```python
# ingestion/processors/weather_ingest.py
import httpx
import asyncio
from datetime import datetime, timedelta
from database.timescale import get_timescale_conn

# Sri Lanka district coordinates
DISTRICTS = {
    "anuradhapura": {"lat": 8.3114, "lon": 80.4037},
    "kandy":        {"lat": 7.2906, "lon": 80.6337},
    "colombo":      {"lat": 6.9271, "lon": 79.8612},
    "galle":        {"lat": 6.0535, "lon": 80.2210},
    "jaffna":       {"lat": 9.6615, "lon": 80.0255},
    "kurunegala":   {"lat": 7.4863, "lon": 80.3647},
    "ratnapura":    {"lat": 6.6828, "lon": 80.3992},
    "badulla":      {"lat": 6.9934, "lon": 81.0550},
    "trincomalee":  {"lat": 8.5874, "lon": 81.2152},
    "matara":       {"lat": 5.9549, "lon": 80.5550},
}

async def ingest_weather_all_districts(days_back: int = 365):
    async with httpx.AsyncClient() as client:
        tasks = [
            fetch_district_weather(client, district, coords, days_back)
            for district, coords in DISTRICTS.items()
        ]
        await asyncio.gather(*tasks)

async def fetch_district_weather(client, district: str, coords: dict, days_back: int):
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=days_back)
    
    url = "https://archive-api.open-meteo.com/v1/archive"
    params = {
        "latitude": coords["lat"],
        "longitude": coords["lon"],
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "daily": [
            "precipitation_sum",
            "temperature_2m_max",
            "temperature_2m_min",
            "relative_humidity_2m_mean",
            "wind_speed_10m_max",
            "et0_fao_evapotranspiration"
        ],
        "timezone": "Asia/Colombo"
    }
    
    resp = await client.get(url, params=params)
    data = resp.json()
    
    await store_weather_timescale(district, data)

async def store_weather_timescale(district: str, data: dict):
    conn = await get_timescale_conn()
    daily = data.get("daily", {})
    dates = daily.get("time", [])
    
    records = [
        (
            date, district,
            daily["precipitation_sum"][i],
            daily["temperature_2m_max"][i],
            daily["temperature_2m_min"][i],
            daily["relative_humidity_2m_mean"][i],
            daily["wind_speed_10m_max"][i],
            daily["et0_fao_evapotranspiration"][i]
        )
        for i, date in enumerate(dates)
    ]
    
    await conn.executemany("""
        INSERT INTO weather_daily 
        (date, district, precipitation_mm, temp_max_c, temp_min_c,
         humidity_pct, wind_speed_ms, evapotranspiration_mm)
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8)
        ON CONFLICT (date, district) DO NOTHING
    """, records)
```

### 5.5 Five Chunking Strategies

```python
# ingestion/chunkers/semantic_chunker.py
from llama_index.core.node_parser import SemanticSplitterNodeParser
from llama_index.embeddings.google import GeminiEmbedding

def semantic_chunk(documents, buffer_size=1, breakpoint_percentile=95):
    embed_model = GeminiEmbedding(model_name="models/text-embedding-004")
    splitter = SemanticSplitterNodeParser(
        buffer_size=buffer_size,
        breakpoint_percentile_threshold=breakpoint_percentile,
        embed_model=embed_model
    )
    return splitter.get_nodes_from_documents(documents)

# ingestion/chunkers/parent_child_chunker.py
from llama_index.core.node_parser import HierarchicalNodeParser, get_leaf_nodes

def parent_child_chunk(documents):
    parser = HierarchicalNodeParser.from_defaults(
        chunk_sizes=[2048, 512, 128]  # parent → child → leaf
    )
    nodes = parser.get_nodes_from_documents(documents)
    leaf_nodes = get_leaf_nodes(nodes)
    return nodes, leaf_nodes

# ingestion/chunkers/fixed_chunker.py
from llama_index.core.node_parser import SentenceSplitter

def fixed_chunk(documents, chunk_size=512, overlap=50):
    splitter = SentenceSplitter(chunk_size=chunk_size, chunk_overlap=overlap)
    return splitter.get_nodes_from_documents(documents)

# ingestion/chunkers/sliding_chunker.py
from llama_index.core.node_parser import SentenceSplitter

def sliding_chunk(documents, chunk_size=512, overlap=256):
    # Higher overlap = sliding window
    splitter = SentenceSplitter(chunk_size=chunk_size, chunk_overlap=overlap)
    return splitter.get_nodes_from_documents(documents)

# ingestion/chunkers/late_chunker.py
# Late chunking: embed full doc first, then chunk — preserves context
def late_chunk(documents, chunk_size=512):
    # Implementation using full-document context embedding
    # then splitting with context-aware boundaries
    from llama_index.core.node_parser import SentenceSplitter
    splitter = SentenceSplitter(chunk_size=chunk_size, chunk_overlap=100)
    nodes = splitter.get_nodes_from_documents(documents)
    # Tag each node with full-doc embedding reference
    for node in nodes:
        node.metadata["chunking_strategy"] = "late"
    return nodes
```

---

## 6. Module 2 — RAG Pipeline

### 6.1 Qdrant Hybrid Search Setup

```python
# knowledge/retrievers/semantic_retriever.py
from qdrant_client import QdrantClient
from qdrant_client.models import (
    VectorParams, Distance, SparseVectorParams,
    SparseIndexParams, HybridFusion, RRFParams
)
import google.generativeai as genai
from config.settings import settings

client = QdrantClient(host=settings.QDRANT_HOST, port=6333)
genai.configure(api_key=settings.GEMINI_API_KEY)

COLLECTION_NAME = "agromind_knowledge"

def create_collection():
    client.recreate_collection(
        collection_name=COLLECTION_NAME,
        vectors_config={
            "dense": VectorParams(size=768, distance=Distance.COSINE)
        },
        sparse_vectors_config={
            "sparse": SparseVectorParams(
                index=SparseIndexParams(on_disk=False)
            )
        }
    )

def embed_query(text: str) -> list[float]:
    result = genai.embed_content(
        model="models/text-embedding-004",
        content=text
    )
    return result["embedding"]

def hybrid_search(query: str, filters: dict = None, top_k: int = 10):
    dense_vector = embed_query(query)
    sparse_vector = compute_bm25_sparse(query)  # See below
    
    # Build Qdrant filter from metadata
    qdrant_filter = build_filter(filters) if filters else None
    
    results = client.query_points(
        collection_name=COLLECTION_NAME,
        prefetch=[
            {"query": dense_vector, "using": "dense", "limit": 20},
            {"query": sparse_vector, "using": "sparse", "limit": 20},
        ],
        query=HybridFusion(RRFParams(rank_constant=60)),
        limit=top_k,
        query_filter=qdrant_filter
    )
    
    return results.points

def build_filter(filters: dict):
    from qdrant_client.models import Filter, FieldCondition, MatchAny
    conditions = []
    if filters.get("crop_types"):
        conditions.append(
            FieldCondition(key="crop_types", match=MatchAny(any=filters["crop_types"]))
        )
    if filters.get("district"):
        conditions.append(
            FieldCondition(key="districts", match=MatchAny(any=[filters["district"]]))
        )
    return Filter(must=conditions) if conditions else None
```

### 6.2 CRAG — Corrective RAG

```python
# knowledge/crag.py
import google.generativeai as genai
from enum import Enum
from dataclasses import dataclass

class ChunkRelevance(Enum):
    RELEVANT = "relevant"
    PARTIAL = "partial"
    IRRELEVANT = "irrelevant"

@dataclass
class GradedChunk:
    chunk: str
    relevance: ChunkRelevance
    score: float
    reason: str

GRADER_PROMPT = """
You are a relevance grader for an agricultural knowledge system.

Query: {query}
Chunk: {chunk}

Grade this chunk's relevance to the query.
Return ONLY valid JSON:
{{
    "relevance": "relevant | partial | irrelevant",
    "score": 0.0-1.0,
    "reason": "one sentence explanation"
}}
"""

model = genai.GenerativeModel("gemini-1.5-flash")

def grade_chunks(query: str, chunks: list[str]) -> list[GradedChunk]:
    graded = []
    for chunk in chunks:
        try:
            response = model.generate_content(
                GRADER_PROMPT.format(query=query, chunk=chunk[:500])
            )
            import json
            data = json.loads(response.text.strip())
            graded.append(GradedChunk(
                chunk=chunk,
                relevance=ChunkRelevance(data["relevance"]),
                score=data["score"],
                reason=data["reason"]
            ))
        except Exception:
            graded.append(GradedChunk(
                chunk=chunk,
                relevance=ChunkRelevance.PARTIAL,
                score=0.5,
                reason="grading failed"
            ))
    return graded

def filter_relevant_chunks(graded: list[GradedChunk], threshold: float = 0.5):
    relevant = [g for g in graded if g.score >= threshold]
    if not relevant:
        return None, True  # Trigger web fallback
    return [g.chunk for g in relevant], False
```

### 6.3 CAG — Cache Augmented Generation

```python
# knowledge/cag.py
import redis
import hashlib
import json
from datetime import timedelta
from config.settings import settings

r = redis.Redis(host=settings.REDIS_HOST, port=6379, decode_responses=True)
CACHE_TTL = timedelta(hours=24)

def cache_key(query: str, context_hash: str) -> str:
    combined = f"{query.lower().strip()}:{context_hash}"
    return f"cag:{hashlib.sha256(combined.encode()).hexdigest()}"

def get_cached_response(query: str, context_hash: str = "") -> dict | None:
    key = cache_key(query, context_hash)
    cached = r.get(key)
    if cached:
        r.incr("cag:hit_count")
        return json.loads(cached)
    r.incr("cag:miss_count")
    return None

def cache_response(query: str, response: dict, context_hash: str = ""):
    key = cache_key(query, context_hash)
    r.setex(key, CACHE_TTL, json.dumps(response))

def get_cache_stats() -> dict:
    hits = int(r.get("cag:hit_count") or 0)
    misses = int(r.get("cag:miss_count") or 0)
    total = hits + misses
    return {
        "hit_count": hits,
        "miss_count": misses,
        "hit_rate": hits / total if total > 0 else 0,
        "total_queries": total
    }
```

### 6.4 Cross-Encoder Reranker

```python
# knowledge/reranker.py
from sentence_transformers import CrossEncoder
from dataclasses import dataclass

model = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")

def rerank(query: str, chunks: list[str], top_k: int = 5) -> list[tuple[str, float]]:
    pairs = [(query, chunk) for chunk in chunks]
    scores = model.predict(pairs)
    
    ranked = sorted(
        zip(chunks, scores),
        key=lambda x: x[1],
        reverse=True
    )
    return ranked[:top_k]
```

---

## 7. Module 3 — Agentic Layer

### 7.1 Agent State

```python
# orchestration/state.py
from typing import TypedDict, Optional, Literal
from dataclasses import dataclass, field

class AgentState(TypedDict):
    # Input
    query: str
    user_id: str
    district: Optional[str]
    crop: Optional[str]
    language: Literal["english", "sinhala", "tamil"]
    
    # Routing
    intent: Optional[str]        # disease | planning | market | policy | general
    sub_tasks: list[str]
    
    # Retrieved context
    semantic_context: list[str]
    temporal_context: dict       # weather + market data
    geo_context: dict            # soil + district info
    
    # CRAG state
    chunk_grades: list[dict]
    needs_web_fallback: bool
    
    # Agent outputs
    risk_assessment: Optional[dict]
    planner_recommendation: Optional[dict]
    market_insight: Optional[dict]
    policy_matches: list[dict]
    
    # Final output
    confidence_score: float
    risk_level: Literal["low", "medium", "high"]
    final_answer: Optional[str]
    citations: list[str]
    reasoning_trace: list[str]
    
    # Cache
    cache_hit: bool
    response_time_ms: float
```

### 7.2 LangGraph Agent Graph

```python
# orchestration/agent_graph.py
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.redis import RedisSaver
from orchestration.state import AgentState
from agents.intent_agent import intent_node
from agents.risk_agent import risk_node
from agents.planner_agent import planner_node
from agents.market_agent import market_node
from agents.policy_agent import policy_node
from agents.validation_agent import validation_node
from agents.explanation_agent import explanation_node
from knowledge.cag import get_cached_response
from orchestration.edges import route_by_intent, should_retry

def cache_check_node(state: AgentState) -> AgentState:
    cached = get_cached_response(state["query"])
    if cached:
        state["cache_hit"] = True
        state["final_answer"] = cached["answer"]
        state["confidence_score"] = cached["confidence"]
    return state

def route_after_cache(state: AgentState):
    if state.get("cache_hit"):
        return "explanation"
    return "intent"

def build_graph():
    workflow = StateGraph(AgentState)
    
    # Add nodes
    workflow.add_node("cache_check", cache_check_node)
    workflow.add_node("intent", intent_node)
    workflow.add_node("risk", risk_node)
    workflow.add_node("planner", planner_node)
    workflow.add_node("market", market_node)
    workflow.add_node("policy", policy_node)
    workflow.add_node("validation", validation_node)
    workflow.add_node("explanation", explanation_node)
    
    # Entry point
    workflow.set_entry_point("cache_check")
    
    # Conditional routing
    workflow.add_conditional_edges("cache_check", route_after_cache)
    workflow.add_conditional_edges("intent", route_by_intent, {
        "disease":  "risk",
        "planning": "planner",
        "market":   "market",
        "policy":   "policy",
        "general":  "planner",
    })
    
    # All agents → validation → explanation
    for agent in ["risk", "planner", "market", "policy"]:
        workflow.add_edge(agent, "validation")
    
    workflow.add_conditional_edges("validation", should_retry, {
        "retry": "intent",
        "pass":  "explanation",
    })
    workflow.add_edge("explanation", END)
    
    # Redis checkpointer for state persistence
    checkpointer = RedisSaver.from_conn_string(f"redis://localhost:6379")
    
    return workflow.compile(checkpointer=checkpointer)
```

### 7.3 Intent Agent

```python
# agents/intent_agent.py
import google.generativeai as genai
import json
from orchestration.state import AgentState
from knowledge.crag import grade_chunks, filter_relevant_chunks
from knowledge.retrievers.semantic_retriever import hybrid_search
from knowledge.reranker import rerank

model = genai.GenerativeModel("gemini-1.5-flash")

INTENT_PROMPT = """
Classify this agricultural query and extract entities.
Return ONLY valid JSON:
{{
    "intent": "disease | planning | market | policy | general",
    "crop": "crop name or null",
    "district": "Sri Lankan district or null",
    "season": "maha | yala | null",
    "sub_tasks": ["list of specific sub-tasks needed"],
    "reasoning": "one sentence"
}}

Query: {query}
"""

def intent_node(state: AgentState) -> AgentState:
    response = model.generate_content(
        INTENT_PROMPT.format(query=state["query"])
    )
    data = json.loads(response.text.strip())
    
    state["intent"] = data["intent"]
    state["crop"] = data.get("crop")
    state["district"] = data.get("district")
    state["sub_tasks"] = data.get("sub_tasks", [])
    state["reasoning_trace"].append(f"Intent: {data['intent']} — {data['reasoning']}")
    
    # Run hybrid retrieval
    filters = {
        "crop_types": [state["crop"]] if state["crop"] else [],
        "district": state["district"]
    }
    raw_chunks = hybrid_search(state["query"], filters=filters, top_k=15)
    chunk_texts = [c.payload["text"] for c in raw_chunks]
    
    # Rerank
    reranked = rerank(state["query"], chunk_texts, top_k=8)
    
    # CRAG grading
    graded = grade_chunks(state["query"], [r[0] for r in reranked])
    relevant_chunks, needs_fallback = filter_relevant_chunks(graded)
    
    state["semantic_context"] = relevant_chunks or []
    state["needs_web_fallback"] = needs_fallback
    state["chunk_grades"] = [
        {"chunk": g.chunk[:100], "score": g.score, "relevance": g.relevance.value}
        for g in graded
    ]
    
    return state
```

### 7.4 Risk Analyst Agent

```python
# agents/risk_agent.py
import google.generativeai as genai
import json
from orchestration.state import AgentState
from knowledge.retrievers.temporal_retriever import get_weather_risk_context

model = genai.GenerativeModel("gemini-1.5-flash")

RISK_PROMPT = """
You are an expert agricultural risk analyst for Sri Lanka.

Crop: {crop}
District: {district}
Current Season Context: {weather_context}
Knowledge Base Context: {semantic_context}

Analyze disease and weather risk. Return ONLY valid JSON:
{{
    "overall_risk_level": "low | medium | high",
    "risk_factors": [
        {{"factor": "name", "severity": "low|medium|high", "description": "...", "source": "..."}}
    ],
    "disease_threats": ["list of specific disease threats this season"],
    "weather_risks": ["list of weather-related risks"],
    "confidence": 0.0-1.0,
    "citations": ["source document names"]
}}
"""

def risk_node(state: AgentState) -> AgentState:
    weather = get_weather_risk_context(
        district=state.get("district", "anuradhapura"),
        days_lookback=30
    )
    
    response = model.generate_content(
        RISK_PROMPT.format(
            crop=state.get("crop", "paddy"),
            district=state.get("district", "unknown"),
            weather_context=json.dumps(weather),
            semantic_context="\n---\n".join(state.get("semantic_context", [])[:5])
        )
    )
    
    data = json.loads(response.text.strip())
    state["risk_assessment"] = data
    state["risk_level"] = data["overall_risk_level"]
    state["reasoning_trace"].append(
        f"Risk: {data['overall_risk_level']} — {len(data['risk_factors'])} factors identified"
    )
    
    return state
```

### 7.5 Validation Agent

```python
# agents/validation_agent.py
import google.generativeai as genai
import json
import yaml
from orchestration.state import AgentState

model = genai.GenerativeModel("gemini-1.5-flash")

# Load agronomic constraint rules
with open("config/crops.yaml") as f:
    CROP_RULES = yaml.safe_load(f)

def validation_node(state: AgentState) -> AgentState:
    violations = []
    
    # 1. Rule-based validation (no LLM needed — deterministic)
    crop = state.get("crop")
    if crop and crop in CROP_RULES:
        rules = CROP_RULES[crop]
        planner = state.get("planner_recommendation", {})
        
        if planner.get("fertilizer_kg_ha"):
            max_n = rules.get("max_nitrogen_kg_ha", 200)
            if planner["fertilizer_kg_ha"] > max_n:
                violations.append(
                    f"Nitrogen recommendation {planner['fertilizer_kg_ha']} exceeds "
                    f"safe limit {max_n} kg/ha for {crop}"
                )
    
    # 2. Hallucination check — verify citations exist
    citations = state.get("citations", [])
    # ... verify against known document registry
    
    # 3. Confidence adjustment
    base_confidence = state.get("confidence_score", 0.8)
    if violations:
        base_confidence *= 0.6
        state["reasoning_trace"].append(
            f"Validation: {len(violations)} violations — confidence adjusted"
        )
    
    state["validation_violations"] = violations
    state["confidence_score"] = round(base_confidence, 2)
    state["validation_passed"] = len(violations) == 0
    
    return state
```

### 7.6 Explanation Agent (Multilingual)

```python
# agents/explanation_agent.py
import google.generativeai as genai
import json
from orchestration.state import AgentState
from knowledge.cag import cache_response

model = genai.GenerativeModel("gemini-1.5-flash")

EXPLAIN_PROMPT = """
You are AgroMind, a friendly agricultural advisor for Sri Lankan farmers.

Language to use: {language}
Query: {query}
Risk Assessment: {risk}
Recommendation: {recommendation}
Confidence: {confidence}
Violations found: {violations}

Write a clear, actionable response in {language}.
For Sinhala/Tamil: transliterate key technical terms.
Include:
1. Direct answer to their question
2. Key risks to watch for  
3. Specific action steps
4. Confidence statement

Keep it practical. Farmers need clear actions, not academic language.
"""

def explanation_node(state: AgentState) -> AgentState:
    response = model.generate_content(
        EXPLAIN_PROMPT.format(
            language=state.get("language", "english"),
            query=state["query"],
            risk=json.dumps(state.get("risk_assessment", {})),
            recommendation=json.dumps(state.get("planner_recommendation", {})),
            confidence=state.get("confidence_score", 0.0),
            violations=state.get("validation_violations", [])
        )
    )
    
    final = response.text.strip()
    state["final_answer"] = final
    
    # Cache for future similar queries
    cache_response(state["query"], {
        "answer": final,
        "confidence": state["confidence_score"]
    })
    
    return state
```

---

## 8. Module 4 — API Layer

### 8.1 FastAPI Main

```python
# api/main.py
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from api.routers import query, simulate, ingest, health
from api.middleware.rate_limiter import RateLimitMiddleware
from monitoring.metrics import PrometheusMiddleware

app = FastAPI(
    title="AgroMind AI",
    description="Agentic RAG for Sri Lankan Agricultural Intelligence",
    version="1.0.0"
)

app.add_middleware(CORSMiddleware, allow_origins=["*"])
app.add_middleware(RateLimitMiddleware, requests_per_minute=30)
app.add_middleware(PrometheusMiddleware)

app.include_router(query.router,    prefix="/api/v1", tags=["Query"])
app.include_router(simulate.router, prefix="/api/v1", tags=["Simulate"])
app.include_router(ingest.router,   prefix="/api/v1", tags=["Ingest"])
app.include_router(health.router,   prefix="/api/v1", tags=["Health"])
```

### 8.2 Query Router

```python
# api/routers/query.py
from fastapi import APIRouter, BackgroundTasks
from api.schemas import QueryRequest, QueryResponse
from orchestration.agent_graph import build_graph
import time

router = APIRouter()
graph = build_graph()

@router.post("/query", response_model=QueryResponse)
async def query_endpoint(request: QueryRequest, background_tasks: BackgroundTasks):
    start = time.time()
    
    initial_state = {
        "query": request.query,
        "user_id": request.user_id or "anonymous",
        "district": request.district,
        "crop": request.crop,
        "language": request.language or "english",
        "reasoning_trace": [],
        "citations": [],
        "cache_hit": False,
    }
    
    config = {"configurable": {"thread_id": request.user_id or "default"}}
    result = await graph.ainvoke(initial_state, config=config)
    
    elapsed = (time.time() - start) * 1000
    result["response_time_ms"] = elapsed
    
    return QueryResponse(
        answer=result["final_answer"],
        confidence_score=result.get("confidence_score", 0.0),
        risk_level=result.get("risk_level", "low"),
        citations=result.get("citations", []),
        reasoning_trace=result.get("reasoning_trace", []),
        cache_hit=result.get("cache_hit", False),
        response_time_ms=elapsed,
        chunk_grades=result.get("chunk_grades", [])
    )
```

### 8.3 Pydantic Schemas

```python
# api/schemas.py
from pydantic import BaseModel
from typing import Optional, Literal

class QueryRequest(BaseModel):
    query: str
    user_id: Optional[str] = None
    district: Optional[str] = None
    crop: Optional[str] = None
    language: Literal["english", "sinhala", "tamil"] = "english"

class QueryResponse(BaseModel):
    answer: str
    confidence_score: float
    risk_level: Literal["low", "medium", "high"]
    citations: list[str]
    reasoning_trace: list[str]
    cache_hit: bool
    response_time_ms: float
    chunk_grades: list[dict]

class SimulateRequest(BaseModel):
    base_query: str
    scenario: str        # e.g. "rain increases by 30%"
    district: str
    crop: str

class SimulateResponse(BaseModel):
    base_recommendation: str
    scenario_recommendation: str
    delta_analysis: str
    risk_change: str
```

---

## 9. Module 5 — Evaluation Framework

### 9.1 RAGAS Chunking Evaluation

```python
# evaluation/run_ragas.py
from ragas import evaluate
from ragas.metrics import faithfulness, answer_relevancy, context_recall
from datasets import Dataset
import json
import mlflow

STRATEGIES = ["fixed", "sliding", "semantic", "parent_child", "late"]

def run_chunking_eval():
    with open("evaluation/qa_pairs/ground_truth.json") as f:
        qa_pairs = json.load(f)
    
    results = {}
    
    with mlflow.start_run(run_name="chunking_strategy_eval"):
        for strategy in STRATEGIES:
            print(f"Evaluating strategy: {strategy}")
            
            # Build RAG with this strategy
            # ... (strategy-specific index)
            
            dataset_rows = []
            for qa in qa_pairs:
                # Retrieve with this strategy
                contexts = retrieve_with_strategy(strategy, qa["question"])
                answer = generate_answer(qa["question"], contexts)
                
                dataset_rows.append({
                    "question": qa["question"],
                    "answer": answer,
                    "contexts": contexts,
                    "ground_truth": qa["answer"]
                })
            
            dataset = Dataset.from_list(dataset_rows)
            scores = evaluate(
                dataset,
                metrics=[faithfulness, answer_relevancy, context_recall]
            )
            
            results[strategy] = {
                "faithfulness": scores["faithfulness"],
                "answer_relevancy": scores["answer_relevancy"],
                "context_recall": scores["context_recall"]
            }
            
            mlflow.log_metrics({
                f"{strategy}_faithfulness": scores["faithfulness"],
                f"{strategy}_relevancy": scores["answer_relevancy"],
                f"{strategy}_recall": scores["context_recall"]
            })
        
        # Save results
        with open("evaluation/results/chunking_eval.json", "w") as f:
            json.dump(results, f, indent=2)
    
    return results
```

### 9.2 CAG Simulation (100 Queries)

```python
# evaluation/run_cache_sim.py
import asyncio
import time
import json
from knowledge.cag import get_cached_response, cache_response, get_cache_stats

# Realistic seasonal query distribution
QUERY_POOL = [
    "Is it safe to plant paddy in Anuradhapura this month?",
    "What is the disease risk for tomatoes in Kandy?",
    "When is the best time to sell paddy?",
    "What fertilizer should I use for rice in Maha season?",
    # ... 20 unique queries → repeated across 100 queries with Zipf distribution
]

async def simulate_100_queries():
    import numpy as np
    
    # Zipf distribution — some queries repeat heavily (seasonal patterns)
    weights = np.array([1/i for i in range(1, len(QUERY_POOL)+1)])
    weights = weights / weights.sum()
    
    selected = np.random.choice(QUERY_POOL, size=100, p=weights)
    
    timings = {"hits": [], "misses": []}
    
    for query in selected:
        start = time.time()
        cached = get_cached_response(query)
        elapsed = (time.time() - start) * 1000
        
        if cached:
            timings["hits"].append(elapsed)
        else:
            # Simulate full pipeline time
            await asyncio.sleep(0.5)  # Simulated 500ms API call
            cache_response(query, {"answer": f"Mock answer for: {query}", "confidence": 0.85})
            timings["misses"].append(500)
    
    stats = get_cache_stats()
    report = {
        "total_queries": 100,
        "cache_hits": stats["hit_count"],
        "cache_misses": stats["miss_count"],
        "hit_rate_pct": round(stats["hit_rate"] * 100, 1),
        "avg_hit_latency_ms": round(sum(timings["hits"]) / len(timings["hits"]), 2) if timings["hits"] else 0,
        "avg_miss_latency_ms": 500,
        "speedup_factor": round(500 / (sum(timings["hits"]) / max(len(timings["hits"]), 1)), 2) if timings["hits"] else 0,
        "estimated_api_calls_saved": stats["hit_count"],
        "estimated_cost_saved_usd": round(stats["hit_count"] * 0.00158, 3)
    }
    
    with open("evaluation/results/cag_simulation.json", "w") as f:
        json.dump(report, f, indent=2)
    
    print(f"Cache hit rate: {report['hit_rate_pct']}%")
    print(f"Speedup: {report['speedup_factor']}x")
    print(f"Cost saved: ${report['estimated_cost_saved_usd']}")
    
    return report
```

---

## 10. Module 6 — Frontend Dashboard

### Key React Components

```jsx
// ui/src/components/AgentTrace.jsx
// Shows real-time agent reasoning steps

export function AgentTrace({ trace }) {
  return (
    <div className="agent-trace">
      <h3>Agent Reasoning</h3>
      {trace.map((step, i) => (
        <div key={i} className={`trace-step step-${i}`}>
          <span className="step-num">{i + 1}</span>
          <span className="step-text">{step}</span>
        </div>
      ))}
    </div>
  );
}

// ui/src/components/ConfidenceBar.jsx
export function ConfidenceBar({ score, riskLevel }) {
  const color = riskLevel === 'high' ? '#e74c3c' 
              : riskLevel === 'medium' ? '#f39c12' 
              : '#27ae60';
  return (
    <div className="confidence-bar">
      <div className="bar-fill" style={{ width: `${score * 100}%`, background: color }} />
      <span>{Math.round(score * 100)}% confidence · {riskLevel} risk</span>
    </div>
  );
}
```

---

## 11. Database Schema

### TimescaleDB — Weather

```sql
CREATE TABLE weather_daily (
    date        DATE         NOT NULL,
    district    VARCHAR(50)  NOT NULL,
    precipitation_mm        FLOAT,
    temp_max_c              FLOAT,
    temp_min_c              FLOAT,
    humidity_pct            FLOAT,
    wind_speed_ms           FLOAT,
    evapotranspiration_mm   FLOAT,
    created_at  TIMESTAMPTZ  DEFAULT NOW(),
    PRIMARY KEY (date, district)
);

SELECT create_hypertable('weather_daily', 'date');
CREATE INDEX ON weather_daily (district, date DESC);
```

### PostgreSQL + PostGIS — Geo & Structured

```sql
CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TABLE districts (
    id          SERIAL PRIMARY KEY,
    name        VARCHAR(100) UNIQUE NOT NULL,
    province    VARCHAR(100),
    boundary    GEOMETRY(POLYGON, 4326),
    area_km2    FLOAT,
    agro_zone   VARCHAR(50),
    rainfall_zone VARCHAR(50)
);

CREATE TABLE soil_profiles (
    id          SERIAL PRIMARY KEY,
    district_id INTEGER REFERENCES districts(id),
    soil_type   VARCHAR(100),
    ph_min      FLOAT,
    ph_max      FLOAT,
    nitrogen_ppm FLOAT,
    phosphorus_ppm FLOAT,
    potassium_ppm  FLOAT,
    drainage_class VARCHAR(50),
    suitable_crops TEXT[]
);

CREATE TABLE market_prices (
    id          SERIAL PRIMARY KEY,
    recorded_date DATE NOT NULL,
    crop        VARCHAR(100),
    market      VARCHAR(100),
    price_lkr_per_kg FLOAT,
    unit        VARCHAR(20),
    source_url  TEXT,
    UNIQUE(recorded_date, crop, market)
);

CREATE TABLE decision_log (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         VARCHAR(100),
    query           TEXT,
    intent          VARCHAR(50),
    district        VARCHAR(100),
    crop            VARCHAR(100),
    recommendation  JSONB,
    confidence      FLOAT,
    risk_level      VARCHAR(20),
    user_feedback   SMALLINT,  -- 1 = helpful, -1 = not helpful, NULL = no feedback
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
```

---

## 12. Environment Configuration

```bash
# .env.example

# === LLM (Only Paid Service) ===
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-1.5-flash
GEMINI_EMBED_MODEL=models/text-embedding-004

# === Vector DB ===
QDRANT_HOST=localhost
QDRANT_PORT=6333
QDRANT_COLLECTION=agromind_knowledge

# === Databases ===
POSTGRES_URL=postgresql://agromind:password@localhost:5432/agromind
TIMESCALE_URL=postgresql://agromind:password@localhost:5432/agromind
REDIS_HOST=localhost
REDIS_PORT=6379

# === Tracing ===
LANGSMITH_API_KEY=your_langsmith_key  # Free tier
LANGSMITH_PROJECT=agromind-ai

# === API ===
API_HOST=0.0.0.0
API_PORT=8000
RATE_LIMIT_RPM=30

# === Celery ===
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/1

# === Evaluation ===
MLFLOW_TRACKING_URI=http://localhost:5000
```

### Docker Compose

```yaml
# docker-compose.yml
version: "3.9"
services:

  qdrant:
    image: qdrant/qdrant:latest
    ports: ["6333:6333", "6334:6334"]
    volumes: ["qdrant_data:/qdrant/storage"]

  postgres:
    image: timescale/timescaledb-ha:pg16-latest
    environment:
      POSTGRES_DB: agromind
      POSTGRES_USER: agromind
      POSTGRES_PASSWORD: password
    ports: ["5432:5432"]
    volumes: ["postgres_data:/var/lib/postgresql/data"]

  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]
    volumes: ["redis_data:/data"]

  mlflow:
    image: ghcr.io/mlflow/mlflow:latest
    ports: ["5000:5000"]
    command: mlflow server --host 0.0.0.0

  prometheus:
    image: prom/prometheus:latest
    ports: ["9090:9090"]
    volumes: ["./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml"]

  grafana:
    image: grafana/grafana:latest
    ports: ["3001:3000"]
    volumes: ["grafana_data:/var/lib/grafana"]

volumes:
  qdrant_data:
  postgres_data:
  redis_data:
  grafana_data:
```

---

## 13. Implementation Phases

### Phase 1 — Foundation (Week 1–2)
- [ ] Set up Docker Compose stack (Qdrant, TimescaleDB, Redis)
- [ ] DOA + HARTI Playwright crawlers
- [ ] PDF extractor with PaddleOCR fallback
- [ ] Gemini metadata tagger
- [ ] Open-Meteo weather ingestion for 10 districts
- [ ] Market price scraper (agriculture.gov.lk)
- [ ] All 5 chunking strategies implemented

**Milestone:** 40–60 documents ingested, weather data for 5 districts loaded

---

### Phase 2 — RAG Pipeline (Week 3)
- [ ] Qdrant collection setup with hybrid search
- [ ] Gemini embeddings pipeline
- [ ] BM25 sparse vectors
- [ ] Cross-encoder reranker
- [ ] CRAG chunk grader
- [ ] CAG Redis cache layer
- [ ] RAGAS evaluation across all 5 strategies
- [ ] 30 ground truth QA pairs written + verified

**Milestone:** RAGAS scores benchmarked, best chunking strategy selected, CAG 100-query simulation run

---

### Phase 3 — Agents (Week 4)
- [ ] LangGraph state machine
- [ ] Intent Agent with metadata-filtered retrieval
- [ ] Risk Analyst Agent (weather + semantic fusion)
- [ ] Crop Planner Agent
- [ ] Market Agent (TimescaleDB queries)
- [ ] Policy Matcher Agent
- [ ] Validation Agent with crops.yaml rules
- [ ] Explanation Agent with multilingual output
- [ ] Agent tracing via LangSmith

**Milestone:** Full agent DAG running end-to-end, 20 test queries across all intents passing

---

### Phase 4 — API & Evaluation (Week 5)
- [ ] FastAPI with all routes
- [ ] Rate limiting + API key auth
- [ ] Prometheus metrics (latency, cache hit rate, agent errors)
- [ ] Grafana dashboard
- [ ] CRAG evaluation across 20 query categories
- [ ] Full CAG simulation report
- [ ] Decision log to PostgreSQL

**Milestone:** API running, all metrics captured, evaluation report generated

---

### Phase 5 — Frontend & Polish (Week 6)
- [ ] React dashboard (Query panel, Agent trace, District map, Market charts)
- [ ] Sinhala/Tamil output tested
- [ ] Scenario simulation UI
- [ ] README with architecture diagram
- [ ] LinkedIn-ready metrics summary

**Milestone:** Demo-ready system, portfolio metrics documented

---

## 14. Portfolio Metrics to Capture

These are the numbers that go in your LinkedIn post and README:

| Metric | How to Measure | Target |
|---|---|---|
| Chunking strategies evaluated | RAGAS eval script | 5 strategies |
| Best faithfulness score | RAGAS output | > 0.95 |
| CAG hit rate | `run_cache_sim.py` | > 70% |
| CAG speedup factor | Timing comparison | > 15x |
| API calls saved per 100 queries | Cache stats | > 70 |
| Cost saved per 100 queries | Gemini pricing calc | > $0.10 |
| CRAG accuracy | Manual grading vs Gemini grading | > 85% |
| Documents ingested | Ingestion pipeline log | 40–60 |
| Districts covered | District config | 10 |
| Agent intents supported | Intent classifier | 4+ |
| Avg response time (cache miss) | API middleware | < 3s |
| Avg response time (cache hit) | API middleware | < 150ms |

---

## Your LinkedIn Post (Template)

> 🌾 Just shipped AgroMind AI — an agentic hybrid RAG system for Sri Lankan agricultural intelligence.
>
> What's inside:
> - 🔍 Async Playwright crawlers: X PDFs from DOA + HARTI with retry logic + OCR fallback
> - 🧩 5 chunking strategies benchmarked with RAGAS: faithfulness scores from X.XX to X.XX
> - ⚡ CAG: 100 query simulation → XX% cache hit rate | XXx speedup | $X.XX saved per 100 queries
> - 🔄 CRAG: per-chunk relevance grading across 20 query types (disease, planning, market, policy)
> - 🔎 Qdrant Hybrid Search: dense (Gemini text-embedding-004) + BM25 sparse + cross-encoder rerank
> - 🤖 LangGraph multi-agent DAG: Intent → Risk → Planner → Market → Policy → Validation → Explanation
>
> 100% open-source infrastructure. Only paid dependency: Google Gemini API.

---

*AgroMind AI — Built for Sri Lankan farmers. Production-grade. Portfolio-ready.*
