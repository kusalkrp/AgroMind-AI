"""
Unit tests for ingestion/processors/metadata_tagger.py

Mocks Gemini API calls to test:
  - Output schema validation (DocumentMetadata Pydantic model)
  - Field normalisation (document_type enum, confidence clamp)
  - Graceful degradation on bad Gemini output
"""
import json
from unittest.mock import MagicMock, patch

import pytest

from ingestion.processors.metadata_tagger import (
    DocumentMetadata,
    MetadataTagger,
    _extract_json,
)


# ── Sample Gemini responses ───────────────────────────────────────────────────

VALID_GEMINI_RESPONSE = {
    "crop_types": ["paddy", "tomato"],
    "districts": ["Kandy", "Galle"],
    "document_type": "advisory",
    "season_relevance": ["Maha", "Yala"],
    "source": "doa.gov.lk",
    "language": "english",
    "confidence": 0.92,
}

MINIMAL_GEMINI_RESPONSE = {
    "crop_types": [],
    "districts": [],
    "document_type": "unknown",
    "season_relevance": [],
    "source": "",
    "language": "english",
    "confidence": 0.1,
}


def _mock_gemini_call(response_dict: dict):
    """Return a patcher that makes _call_gemini return response_dict."""
    return patch(
        "ingestion.processors.metadata_tagger._call_gemini",
        return_value=response_dict,
    )


# ── Tests: DocumentMetadata schema ────────────────────────────────────────────

class TestDocumentMetadataSchema:

    def test_valid_response_parses_correctly(self):
        meta = DocumentMetadata(**VALID_GEMINI_RESPONSE)
        assert meta.crop_types == ["paddy", "tomato"]
        assert meta.districts == ["Kandy", "Galle"]
        assert meta.document_type == "advisory"
        assert meta.season_relevance == ["Maha", "Yala"]
        assert meta.source == "doa.gov.lk"
        assert meta.confidence == 0.92

    def test_invalid_document_type_normalised_to_unknown(self):
        """Unknown document_type values should be normalised to 'unknown'."""
        data = {**VALID_GEMINI_RESPONSE, "document_type": "newsletter"}
        meta = DocumentMetadata(**data)
        assert meta.document_type == "unknown"

    def test_confidence_clamped_to_zero_one(self):
        """Confidence values outside [0, 1] should be clamped."""
        above = DocumentMetadata(**{**VALID_GEMINI_RESPONSE, "confidence": 1.5})
        below = DocumentMetadata(**{**VALID_GEMINI_RESPONSE, "confidence": -0.3})
        assert above.confidence == 1.0
        assert below.confidence == 0.0

    def test_all_allowed_document_types_accepted(self):
        allowed = [
            "advisory", "market_price", "weather_report",
            "research_paper", "policy", "extension_guide", "unknown",
        ]
        for doc_type in allowed:
            meta = DocumentMetadata(**{**VALID_GEMINI_RESPONSE, "document_type": doc_type})
            assert meta.document_type == doc_type

    def test_default_values_on_empty_init(self):
        meta = DocumentMetadata()
        assert meta.crop_types == []
        assert meta.districts == []
        assert meta.document_type == "unknown"
        assert meta.confidence == 0.0


# ── Tests: MetadataTagger.tag() ───────────────────────────────────────────────

class TestMetadataTagger:

    def test_tag_returns_document_metadata_instance(self):
        with _mock_gemini_call(VALID_GEMINI_RESPONSE):
            tagger = MetadataTagger()
            result = tagger.tag("Some agricultural text about paddy in Kandy.")

        assert isinstance(result, DocumentMetadata)

    def test_tag_populated_fields_from_gemini(self):
        with _mock_gemini_call(VALID_GEMINI_RESPONSE):
            tagger = MetadataTagger()
            result = tagger.tag("Paddy cultivation advisory for Maha season.")

        assert result.crop_types == ["paddy", "tomato"]
        assert result.document_type == "advisory"
        assert result.confidence == 0.92

    def test_tag_empty_text_returns_default_metadata(self):
        """Empty text should be handled gracefully without calling Gemini."""
        with patch("ingestion.processors.metadata_tagger._call_gemini") as mock_call:
            tagger = MetadataTagger()
            result = tagger.tag("   ")

        mock_call.assert_not_called()
        assert isinstance(result, DocumentMetadata)
        assert result.document_type == "unknown"
        assert result.confidence == 0.0

    def test_tag_handles_invalid_json_from_gemini(self):
        """If _call_gemini returns garbage, tag() should return default metadata."""
        with patch(
            "ingestion.processors.metadata_tagger._call_gemini",
            side_effect=json.JSONDecodeError("bad json", "", 0),
        ):
            tagger = MetadataTagger()
            result = tagger.tag("Valid agricultural text here.")

        assert isinstance(result, DocumentMetadata)
        assert result.document_type == "unknown"

    def test_tag_handles_gemini_api_exception(self):
        """If Gemini raises an exception, tag() should return default metadata."""
        with patch(
            "ingestion.processors.metadata_tagger._call_gemini",
            side_effect=Exception("API quota exceeded"),
        ):
            tagger = MetadataTagger()
            result = tagger.tag("Some text.")

        assert isinstance(result, DocumentMetadata)
        assert result.confidence == 0.0

    def test_tag_batch_returns_list_of_metadata(self):
        texts = [
            "Paddy advisory for Maha season in Kandy.",
            "Tomato prices in Colombo market.",
        ]
        with _mock_gemini_call(VALID_GEMINI_RESPONSE):
            tagger = MetadataTagger()
            results = tagger.tag_batch(texts)

        assert len(results) == len(texts)
        assert all(isinstance(r, DocumentMetadata) for r in results)


# ── Tests: _extract_json helper ───────────────────────────────────────────────

class TestExtractJson:

    def test_plain_json_string(self):
        raw = json.dumps(VALID_GEMINI_RESPONSE)
        parsed = _extract_json(raw)
        assert parsed["document_type"] == "advisory"

    def test_json_with_markdown_fences(self):
        raw = f"```json\n{json.dumps(VALID_GEMINI_RESPONSE)}\n```"
        parsed = _extract_json(raw)
        assert parsed["confidence"] == 0.92

    def test_json_with_plain_code_fence(self):
        raw = f"```\n{json.dumps(MINIMAL_GEMINI_RESPONSE)}\n```"
        parsed = _extract_json(raw)
        assert parsed["document_type"] == "unknown"

    def test_invalid_json_raises_json_decode_error(self):
        with pytest.raises(json.JSONDecodeError):
            _extract_json("this is not json at all")
