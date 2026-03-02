"""
Global pytest configuration.

Sets required environment variables and sys.modules stubs BEFORE any app
module is imported, so tests can run without heavy optional packages
(PyMuPDF, PaddleOCR, llama-index-embeddings-google, etc.).

All actual calls to these packages are mocked inside individual tests.
"""
import os
import sys
from unittest.mock import MagicMock

# ── Required env vars (before pydantic-settings reads them) ───────────────────
os.environ.setdefault("GEMINI_API_KEY", "test-key-unit-tests")
os.environ.setdefault("POSTGRES_URL", "postgresql://agromind:agromind_secret@localhost:5432/agromind")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("CELERY_BROKER_URL", "redis://localhost:6379/0")
os.environ.setdefault("CELERY_RESULT_BACKEND", "redis://localhost:6379/1")

# ── sys.modules stubs for heavy packages not required in the test venv ────────
# fitz / PyMuPDF — used inside extract_pdf(); patched per-test
if "fitz" not in sys.modules:
    _fitz = MagicMock()
    _fitz.Matrix = MagicMock(return_value=MagicMock())
    sys.modules["fitz"] = _fitz

# PaddleOCR — imported lazily; stub prevents ImportError during collection
if "paddleocr" not in sys.modules:
    sys.modules["paddleocr"] = MagicMock()
if "paddlepaddle" not in sys.modules:
    sys.modules["paddlepaddle"] = MagicMock()

# llama_index.embeddings.google — used by SemanticSplitterNodeParser init
if "llama_index.embeddings.google" not in sys.modules:
    _gem_embed_mod = MagicMock()
    _gem_embed_mod.GeminiEmbedding = MagicMock
    sys.modules["llama_index.embeddings.google"] = _gem_embed_mod
