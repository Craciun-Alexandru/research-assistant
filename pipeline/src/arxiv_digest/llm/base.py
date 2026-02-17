"""
Abstract base class for LLM clients and shared exceptions.
"""

from abc import ABC, abstractmethod


class LLMError(Exception):
    """Base exception for LLM client errors."""


class LLMRateLimitError(LLMError):
    """Raised when the LLM API returns a rate-limit (429) response."""


class ChatSession(ABC):
    """Abstract multi-turn chat session."""

    @abstractmethod
    def send(self, message: str) -> str:
        """Send a message and return the model's text response.

        Args:
            message: The user message to send.

        Returns:
            The model's text reply.
        """


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

    @abstractmethod
    def chat(self, system_prompt: str, *, model: str | None = None) -> ChatSession:
        """Start a multi-turn chat session.

        Args:
            system_prompt: System instruction for the conversation.
            model: Optional model override (uses the client default when *None*).

        Returns:
            A ChatSession instance for multi-turn conversation.
        """
