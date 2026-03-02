"""
PDF Extractor — primary extraction with PyMuPDF (fitz).
Falls back to PaddleOCR when page text is sparse (< 50 chars).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from loguru import logger

# PaddleOCR is imported lazily to avoid heavy import cost when OCR is not needed
_paddle_ocr = None
OCR_TEXT_THRESHOLD = 50  # chars per page below which OCR is triggered


@dataclass
class ExtractedPage:
    page_num: int
    text: str
    used_ocr: bool


@dataclass
class ExtractedDocument:
    filepath: Path
    pages: list[ExtractedPage] = field(default_factory=list)
    total_pages: int = 0
    ocr_page_count: int = 0
    error: Optional[str] = None

    @property
    def full_text(self) -> str:
        return "\n\n".join(p.text for p in self.pages if p.text.strip())

    @property
    def success(self) -> bool:
        return self.error is None and len(self.pages) > 0


def _get_paddle_ocr():
    """Lazy-load PaddleOCR to avoid startup cost when not needed."""
    global _paddle_ocr
    if _paddle_ocr is None:
        from paddleocr import PaddleOCR  # type: ignore

        _paddle_ocr = PaddleOCR(use_angle_cls=True, lang="en", show_log=False)
    return _paddle_ocr


def _ocr_page_image(img_bytes: bytes) -> str:
    """Run PaddleOCR on a page rendered as an image (bytes)."""
    import io
    import numpy as np
    from PIL import Image  # type: ignore

    ocr = _get_paddle_ocr()
    image = Image.open(io.BytesIO(img_bytes)).convert("RGB")
    img_array = np.array(image)
    result = ocr.ocr(img_array, cls=True)

    lines = []
    if result:
        for block in result:
            if block:
                for line in block:
                    if line and len(line) >= 2:
                        text_info = line[1]
                        if isinstance(text_info, (list, tuple)) and len(text_info) >= 1:
                            lines.append(str(text_info[0]))
    return "\n".join(lines)


def extract_pdf(filepath: Path | str) -> ExtractedDocument:
    """
    Extract text from a PDF file.

    Strategy:
    1. Open with PyMuPDF (fitz)
    2. For each page: extract text with fitz.get_text()
    3. If extracted text < OCR_TEXT_THRESHOLD chars, render page to image and OCR it

    Args:
        filepath: Path to the PDF file.

    Returns:
        ExtractedDocument with per-page text and metadata.
    """
    import fitz  # PyMuPDF  # type: ignore

    filepath = Path(filepath)
    doc_result = ExtractedDocument(filepath=filepath)

    if not filepath.exists():
        doc_result.error = f"File not found: {filepath}"
        logger.error(doc_result.error)
        return doc_result

    try:
        pdf = fitz.open(str(filepath))
        doc_result.total_pages = len(pdf)

        for page_num in range(len(pdf)):
            page = pdf[page_num]
            text = page.get_text("text").strip()
            used_ocr = False

            if len(text) < OCR_TEXT_THRESHOLD:
                logger.debug(
                    f"{filepath.name} page {page_num + 1}: "
                    f"sparse text ({len(text)} chars), running OCR"
                )
                try:
                    # Render page to PNG bytes at 2x scale for better OCR accuracy
                    mat = fitz.Matrix(2, 2)
                    pix = page.get_pixmap(matrix=mat)
                    img_bytes = pix.tobytes("png")
                    text = _ocr_page_image(img_bytes)
                    used_ocr = True
                    doc_result.ocr_page_count += 1
                except Exception as ocr_exc:
                    logger.warning(
                        f"{filepath.name} page {page_num + 1}: OCR failed: {ocr_exc}. "
                        "Using sparse fitz text."
                    )

            doc_result.pages.append(
                ExtractedPage(page_num=page_num + 1, text=text, used_ocr=used_ocr)
            )

        pdf.close()
        logger.info(
            f"Extracted {doc_result.total_pages} pages from {filepath.name} "
            f"({doc_result.ocr_page_count} OCR pages)"
        )

    except Exception as exc:
        doc_result.error = f"Extraction failed: {exc}"
        logger.error(f"{filepath.name}: {doc_result.error}")

    return doc_result
