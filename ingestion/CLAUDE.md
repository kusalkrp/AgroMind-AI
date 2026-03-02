# CLAUDE.md — ingestion/

This file provides guidance to Claude Code (claude.ai/code) when working in this directory.

## Pipeline Flow

```
crawlers/ → processors/ → chunkers/ → pipeline.py (Celery orchestration)
```

`pipeline.py` is the only entry point. It chains all steps as Celery tasks. Do not call crawler or processor functions directly in production — they must go through the task queue.

## Crawlers (`crawlers/`)

All crawlers are async and use Playwright. Follow this pattern:

```python
async def crawl_<source>(output_dir: str = "data/raw/<source>") -> List[str]:
    """Returns list of downloaded file paths."""
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ...
        await browser.close()
    return downloaded_paths
```

- `wait_until="networkidle"` + `asyncio.sleep(2)` between page loads (off-peak rate limiting)
- 3 retries with exponential backoff (`2 ** attempt` seconds) on download failures
- Skip already-downloaded files (check `filepath.exists()` before downloading)
- Rate limit: `asyncio.sleep(1)` between downloads

| Crawler | Target | Output dir |
|---|---|---|
| `doa_crawler.py` | doa.gov.lk PDFs | `data/raw/doa/` |
| `harti_crawler.py` | harti.gov.lk PDFs | `data/raw/harti/` |
| `market_price_scraper.py` | agriculture.gov.lk price tables | `data/raw/market/` |

## PDF Processor (`processors/pdf_extractor.py`)

OCR fallback threshold: **< 50 chars** of text on a page → treat as scanned, use PaddleOCR.

```python
# OCR fallback decision
text = page.get_text("text").strip()
if len(text) < 50:
    # render at 200 DPI → save to /tmp/page_N.png → run PaddleOCR
```

Returns `ExtractedDocument(filename, text, page_count, is_ocr, metadata)`.

## Metadata Tagger (`processors/metadata_tagger.py`)

Uses Gemini to auto-tag documents. Output fields that must always be present:

```json
{
  "crop_types": ["paddy", "tomato"],
  "districts": ["anuradhapura", "kandy"],
  "document_type": "pest_management | crop_guide | market_report | weather | policy",
  "season_relevance": ["maha", "yala"],
  "source": "doa | harti | market | weather"
}
```

These fields map directly to Qdrant point metadata and are used for filtered retrieval.

## Chunkers (`chunkers/`)

Five strategies, all return `List[Node]` (LlamaIndex nodes):

| File | Strategy | Key params |
|---|---|---|
| `fixed_chunker.py` | SentenceSplitter | `chunk_size=512, overlap=50` |
| `sliding_chunker.py` | SentenceSplitter | `chunk_size=512, overlap=256` |
| `semantic_chunker.py` | SemanticSplitterNodeParser | `buffer_size=1, breakpoint_percentile=95` |
| `parent_child_chunker.py` | HierarchicalNodeParser | `chunk_sizes=[2048, 512, 128]` |
| `late_chunker.py` | SentenceSplitter + doc-level metadata | `chunk_size=512, overlap=100` |

Tag every node with `node.metadata["chunking_strategy"] = "<strategy_name>"` so RAGAS results can be traced back to strategy.

The best strategy (selected after RAGAS evaluation) should be set in `config/settings.py` as `CHUNKING_STRATEGY` and used by `pipeline.py` for production ingestion.

## Weather Ingestion (`processors/weather_ingest.py`)

- Source: Open-Meteo API (free, no key required)
- 10 Sri Lankan districts: Anuradhapura, Kandy, Colombo, Galle, Jaffna, Kurunegala, Ratnapura, Badulla, Trincomalee, Hambantota
- Writes to `weather_daily` hypertable in TimescaleDB
- Scheduled via Celery Beat — weekly full pull, daily delta

## Celery Task Naming

Tasks must be named with the module path for discoverability:

```python
@celery_app.task(name="ingestion.crawlers.doa.crawl")
@celery_app.task(name="ingestion.processors.pdf.extract")
@celery_app.task(name="ingestion.pipeline.ingest_document")
```
