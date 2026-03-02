"""
Unit tests for ingestion/processors/pdf_extractor.py

Tests the OCR threshold logic and core extraction behaviour without
requiring actual PDF files or a GPU-backed PaddleOCR installation.
"""
import io
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from ingestion.processors.pdf_extractor import (
    ExtractedDocument,
    ExtractedPage,
    OCR_TEXT_THRESHOLD,
    extract_pdf,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

SAMPLE_TEXT_RICH = "A" * 200       # > OCR_TEXT_THRESHOLD → no OCR
SAMPLE_TEXT_SPARSE = "AB"          # < OCR_TEXT_THRESHOLD → triggers OCR
OCR_FALLBACK_TEXT = "OCR extracted text from image"


def _make_mock_page(text: str) -> MagicMock:
    """Create a mock fitz.Page that returns `text` from get_text()."""
    page = MagicMock()
    page.get_text.return_value = text
    # Mock pixmap for OCR path
    pix = MagicMock()
    pix.tobytes.return_value = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100  # fake PNG bytes
    page.get_pixmap.return_value = pix
    return page


def _make_mock_pdf(pages: list[str]) -> MagicMock:
    """Create a mock fitz.Document with the given per-page texts."""
    mock_pdf = MagicMock()
    mock_pdf.__len__ = MagicMock(return_value=len(pages))
    mock_pdf.__iter__ = MagicMock(return_value=iter([_make_mock_page(t) for t in pages]))
    mock_pdf.__getitem__ = MagicMock(side_effect=lambda i: _make_mock_page(pages[i]))
    mock_pdf.close = MagicMock()
    return mock_pdf


# ── Tests: OCR threshold logic ────────────────────────────────────────────────

class TestOCRThreshold:

    def test_rich_text_page_skips_ocr(self, tmp_path):
        """Pages with text >= threshold should NOT trigger OCR."""
        pdf_path = tmp_path / "rich.pdf"
        pdf_path.touch()

        mock_pdf = _make_mock_pdf([SAMPLE_TEXT_RICH])

        with patch("fitz.open", return_value=mock_pdf), \
             patch.object(Path, "exists", return_value=True), \
             patch("ingestion.processors.pdf_extractor._ocr_page_image") as mock_ocr:

            result = extract_pdf(pdf_path)

        mock_ocr.assert_not_called()
        assert result.success
        assert result.ocr_page_count == 0
        assert result.pages[0].used_ocr is False

    def test_sparse_text_page_triggers_ocr(self, tmp_path):
        """Pages with text < threshold should trigger PaddleOCR."""
        pdf_path = tmp_path / "sparse.pdf"
        pdf_path.touch()

        mock_pdf = _make_mock_pdf([SAMPLE_TEXT_SPARSE])

        with patch("fitz.open", return_value=mock_pdf), \
             patch.object(Path, "exists", return_value=True), \
             patch("ingestion.processors.pdf_extractor._ocr_page_image",
                   return_value=OCR_FALLBACK_TEXT) as mock_ocr:

            result = extract_pdf(pdf_path)

        mock_ocr.assert_called_once()
        assert result.success
        assert result.ocr_page_count == 1
        assert result.pages[0].used_ocr is True
        assert result.pages[0].text == OCR_FALLBACK_TEXT

    def test_threshold_boundary_exact_value(self, tmp_path):
        """Text exactly at threshold length should NOT trigger OCR."""
        pdf_path = tmp_path / "boundary.pdf"
        pdf_path.touch()

        boundary_text = "X" * OCR_TEXT_THRESHOLD  # exactly at threshold
        mock_pdf = _make_mock_pdf([boundary_text])

        with patch("fitz.open", return_value=mock_pdf), \
             patch.object(Path, "exists", return_value=True), \
             patch("ingestion.processors.pdf_extractor._ocr_page_image") as mock_ocr:

            result = extract_pdf(pdf_path)

        mock_ocr.assert_not_called()
        assert result.pages[0].used_ocr is False

    def test_mixed_pages_partial_ocr(self, tmp_path):
        """Document with both rich and sparse pages → OCR only on sparse ones."""
        pdf_path = tmp_path / "mixed.pdf"
        pdf_path.touch()

        page_texts = [SAMPLE_TEXT_RICH, SAMPLE_TEXT_SPARSE, SAMPLE_TEXT_RICH]
        mock_pdf = _make_mock_pdf(page_texts)

        with patch("fitz.open", return_value=mock_pdf), \
             patch.object(Path, "exists", return_value=True), \
             patch("ingestion.processors.pdf_extractor._ocr_page_image",
                   return_value=OCR_FALLBACK_TEXT):

            result = extract_pdf(pdf_path)

        assert result.total_pages == 3
        assert result.ocr_page_count == 1
        assert result.pages[0].used_ocr is False
        assert result.pages[1].used_ocr is True
        assert result.pages[2].used_ocr is False


# ── Tests: Error handling ─────────────────────────────────────────────────────

class TestErrorHandling:

    def test_missing_file_returns_error(self, tmp_path):
        """Extracting a non-existent file should return an error document."""
        result = extract_pdf(tmp_path / "nonexistent.pdf")

        assert not result.success
        assert result.error is not None
        assert "not found" in result.error.lower()
        assert result.pages == []

    def test_ocr_failure_falls_back_to_sparse_text(self, tmp_path):
        """When OCR throws, the page should keep the sparse fitz text."""
        pdf_path = tmp_path / "ocr_fail.pdf"
        pdf_path.touch()

        mock_pdf = _make_mock_pdf([SAMPLE_TEXT_SPARSE])

        with patch("fitz.open", return_value=mock_pdf), \
             patch.object(Path, "exists", return_value=True), \
             patch("ingestion.processors.pdf_extractor._ocr_page_image",
                   side_effect=RuntimeError("GPU out of memory")):

            result = extract_pdf(pdf_path)

        # Should not crash; sparse text used as fallback
        assert result.success
        assert result.pages[0].text == SAMPLE_TEXT_SPARSE
        assert result.pages[0].used_ocr is False  # OCR failed, so flag is False

    def test_fitz_open_failure_returns_error(self, tmp_path):
        """fitz.open() raising an exception should be caught gracefully."""
        pdf_path = tmp_path / "corrupt.pdf"
        pdf_path.touch()

        with patch("fitz.open", side_effect=Exception("file corrupted")), \
             patch.object(Path, "exists", return_value=True):

            result = extract_pdf(pdf_path)

        assert not result.success
        assert "Extraction failed" in result.error


# ── Tests: ExtractedDocument properties ──────────────────────────────────────

class TestExtractedDocument:

    def test_full_text_joins_pages(self):
        doc = ExtractedDocument(
            filepath=Path("test.pdf"),
            pages=[
                ExtractedPage(page_num=1, text="Page one text.", used_ocr=False),
                ExtractedPage(page_num=2, text="Page two text.", used_ocr=False),
            ],
            total_pages=2,
        )
        assert "Page one text." in doc.full_text
        assert "Page two text." in doc.full_text

    def test_empty_pages_are_excluded_from_full_text(self):
        doc = ExtractedDocument(
            filepath=Path("test.pdf"),
            pages=[
                ExtractedPage(page_num=1, text="Valid text", used_ocr=False),
                ExtractedPage(page_num=2, text="   ", used_ocr=False),
            ],
            total_pages=2,
        )
        assert "   " not in doc.full_text
        assert doc.full_text.strip() == "Valid text"

    def test_success_false_when_error_set(self):
        doc = ExtractedDocument(filepath=Path("x.pdf"), error="some error")
        assert not doc.success
