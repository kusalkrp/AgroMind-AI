"""
Shared Gemini client helper — new google-genai SDK.
All agents import call_gemini() from here instead of instantiating a client each time.
"""
from __future__ import annotations

from google import genai
from google.genai import types
from loguru import logger

from config.settings import settings

_client: genai.Client | None = None


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client(api_key=settings.gemini_api_key)
    return _client


def call_gemini(prompt: str, temperature: float = 0.1) -> str:
    """
    Call Gemini and return the response text.

    Args:
        prompt: Full prompt string (system + user combined, or user-only).
        temperature: Sampling temperature (default 0.1 for structured outputs).

    Returns:
        Response text string.

    Raises:
        Exception: Propagates on API errors (callers handle with try/except).
    """
    client = _get_client()
    response = client.models.generate_content(
        model=settings.gemini_model,
        contents=prompt,
        config=types.GenerateContentConfig(temperature=temperature),
    )
    return response.text
