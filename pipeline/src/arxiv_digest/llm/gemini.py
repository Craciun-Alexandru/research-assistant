"""
Gemini LLM client using the google-genai SDK.
"""

import json
import time

from google import genai
from google.genai import types

from arxiv_digest.llm.base import LLMClient, LLMError, LLMRateLimitError

_DEFAULT_MODEL = "gemini-2.0-flash"
_MAX_RETRIES = 3
_INITIAL_BACKOFF = 2  # seconds


class GeminiClient(LLMClient):
    """Gemini backend via ``google.genai.Client``."""

    default_model: str = _DEFAULT_MODEL

    def __init__(self, api_key: str) -> None:
        if not api_key:
            raise LLMError("GEMINI_API_KEY is not set or empty")
        self._client = genai.Client(api_key=api_key)

    # ------------------------------------------------------------------
    def complete_json(
        self,
        prompt: str,
        schema: dict,
        *,
        model: str | None = None,
    ) -> dict:
        """Call Gemini and return structured JSON."""
        model = model or self.default_model

        last_exc: Exception | None = None
        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                response = self._client.models.generate_content(
                    model=model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=schema,
                    ),
                )
                return json.loads(response.text)

            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                err_str = str(exc).lower()
                is_retryable = "429" in err_str or "500" in err_str or "503" in err_str
                if not is_retryable or attempt == _MAX_RETRIES:
                    break
                wait = _INITIAL_BACKOFF * (2 ** (attempt - 1))
                print(f"  Retryable error (attempt {attempt}/{_MAX_RETRIES}), waiting {wait}s...")
                time.sleep(wait)

        # All retries exhausted or non-retryable error
        err_str = str(last_exc).lower()
        if "429" in err_str:
            raise LLMRateLimitError(
                f"Rate limited after {_MAX_RETRIES} retries: {last_exc}"
            ) from last_exc
        raise LLMError(f"Gemini API error: {last_exc}") from last_exc
