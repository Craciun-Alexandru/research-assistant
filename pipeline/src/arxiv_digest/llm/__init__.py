"""
LLM client factory.

Usage::

    from arxiv_digest.llm import create_client
    client = create_client("gemini", api_key="...")
"""

from arxiv_digest.llm.base import ChatSession, LLMClient, LLMError, LLMRateLimitError


def create_client(provider: str, **kwargs: object) -> LLMClient:
    """Instantiate an LLM client for the given *provider*.

    Args:
        provider: Backend name (currently only ``"gemini"``).
        **kwargs: Forwarded to the provider constructor (e.g. ``api_key``).

    Returns:
        An ``LLMClient`` instance.

    Raises:
        ValueError: If the provider is unknown.
    """
    if provider == "gemini":
        from arxiv_digest.llm.gemini import GeminiClient

        return GeminiClient(**kwargs)  # type: ignore[arg-type]

    raise ValueError(f"Unknown LLM provider: {provider!r}")


__all__ = ["create_client", "ChatSession", "LLMClient", "LLMError", "LLMRateLimitError"]
