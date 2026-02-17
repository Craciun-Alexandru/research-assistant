"""
Abstract base class for LLM clients and shared exceptions.
"""

from abc import ABC, abstractmethod


class LLMError(Exception):
    """Base exception for LLM client errors."""


class LLMRateLimitError(LLMError):
    """Raised when the LLM API returns a rate-limit (429) response."""


class LLMClient(ABC):
    """Abstract interface for language-model backends."""

    @abstractmethod
    def complete_json(
        self,
        prompt: str,
        schema: dict,
        *,
        model: str | None = None,
    ) -> dict:
        """Send a prompt and return a parsed JSON response conforming to *schema*.

        Args:
            prompt: The user prompt to send.
            schema: JSON-schema dict describing the expected response shape.
            model: Optional model override (uses the client default when *None*).

        Returns:
            Parsed JSON dict from the model response.

        Raises:
            LLMError: On non-retryable API failures.
            LLMRateLimitError: On 429 / rate-limit responses (after retries exhausted).
        """
