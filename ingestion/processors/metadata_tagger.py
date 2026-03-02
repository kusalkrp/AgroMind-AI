"""
Metadata Tagger — uses Gemini 1.5 Flash to extract structured agronomic metadata
from document text chunks. Reads prompt from config/prompts/metadata_prompt.yaml.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Optional

import yaml
from loguru import logger
from pydantic import BaseModel, Field, field_validator
from tenacity import retry, stop_after_attempt, wait_exponential

from config.settings import settings

PROMPT_PATH = settings.prompts_dir / "metadata_prompt.yaml"


class DocumentMetadata(BaseModel):
    """Structured metadata extracted from a document chunk by Gemini."""

    crop_types: list[str] = Field(default_factory=list)
    districts: list[str] = Field(default_factory=list)
    document_type: str = "unknown"
    season_relevance: list[str] = Field(default_factory=list)
    source: str = ""
    language: str = "english"
    confidence: float = 0.0

    @field_validator("document_type")
    @classmethod
    def validate_doc_type(cls, v: str) -> str:
        allowed = {
            "advisory", "market_price", "weather_report",
            "research_paper", "policy", "extension_guide", "unknown",
        }
        return v if v in allowed else "unknown"

    @field_validator("confidence")
    @classmethod
    def clamp_confidence(cls, v: float) -> float:
        return max(0.0, min(1.0, v))


def _load_prompt() -> dict:
    with open(PROMPT_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _extract_json(text: str) -> dict:
    """Extract JSON object from model response, stripping markdown fences if present."""
    # Strip ```json ... ``` wrappers
    clean = re.sub(r"```(?:json)?\s*", "", text).strip().rstrip("`").strip()
    return json.loads(clean)


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=2, max=20),
    reraise=True,
)
def _call_gemini(text: str, prompt_config: dict) -> dict:
    """Call Gemini API with the metadata extraction prompt."""
    import google.generativeai as genai  # type: ignore

    genai.configure(api_key=settings.gemini_api_key)
    model = genai.GenerativeModel(
        model_name=settings.gemini_model,
        system_instruction=prompt_config["system"],
    )

    user_msg = prompt_config["user_template"].format(text=text[:4000])  # cap at 4k chars
    response = model.generate_content(user_msg)
    return _extract_json(response.text)


class MetadataTagger:
    """Tags document chunks with structured agronomic metadata using Gemini."""

    def __init__(self) -> None:
        self._prompt_config: Optional[dict] = None

    @property
    def prompt_config(self) -> dict:
        if self._prompt_config is None:
            self._prompt_config = _load_prompt()
        return self._prompt_config

    def tag(self, text: str) -> DocumentMetadata:
        """
        Tag a document text chunk with metadata.

        Args:
            text: Raw document text (up to ~4000 chars used for tagging).

        Returns:
            DocumentMetadata Pydantic model.
        """
        if not text.strip():
            logger.warning("Empty text passed to MetadataTagger — returning default metadata")
            return DocumentMetadata()

        try:
            raw = _call_gemini(text, self.prompt_config)
            metadata = DocumentMetadata(**raw)
            logger.debug(
                f"Tagged document: type={metadata.document_type}, "
                f"crops={metadata.crop_types}, confidence={metadata.confidence:.2f}"
            )
            return metadata
        except json.JSONDecodeError as exc:
            logger.error(f"Gemini returned invalid JSON: {exc}")
            return DocumentMetadata()
        except Exception as exc:
            logger.error(f"Metadata tagging failed: {exc}")
            return DocumentMetadata()

    def tag_batch(self, texts: list[str]) -> list[DocumentMetadata]:
        """Tag multiple text chunks. Sequential to respect API rate limits."""
        return [self.tag(t) for t in texts]
