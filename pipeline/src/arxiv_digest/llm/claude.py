"""
Claude LLM client using the anthropic SDK.
"""

import json
import time

import anthropic

from arxiv_digest.llm.base import ChatSession, LLMClient, LLMError, LLMRateLimitError

_DEFAULT_MODEL = "claude-haiku-4-5-20251001"
_MAX_RETRIES = 3
_INITIAL_BACKOFF = 2  # seconds
_MAX_TOKENS = 8192


class ClaudeClient(LLMClient):
    """Claude backend via the ``anthropic`` SDK."""

    default_model: str = _DEFAULT_MODEL

    def __init__(self, api_key: str) -> None:
        if not api_key:
            raise LLMError("ANTHROPIC_API_KEY is not set or empty")
        self._client = anthropic.Anthropic(api_key=api_key)

    # ------------------------------------------------------------------
    def complete_json(
        self,
        prompt: str,
        schema: dict,
        *,
        model: str | None = None,
    ) -> dict:
        """Call Claude and return structured JSON.

        The schema is embedded in the system prompt so Claude knows the
        expected response shape.
        """
        model = model or self.default_model
        system = (
            "You are a precise JSON responder. "
            "Always respond with valid JSON only — no markdown fences, no explanation. "
            f"The response must conform to this JSON schema:\n{json.dumps(schema, indent=2)}"
        )

        last_exc: Exception | None = None
        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                response = self._client.messages.create(
                    model=model,
                    max_tokens=_MAX_TOKENS,
                    system=system,
                    messages=[{"role": "user", "content": prompt}],
                )
                text = response.content[0].text.strip()
                # Strip markdown fences if the model adds them anyway
                if text.startswith("```"):
                    lines = text.split("\n")
                    text = "\n".join(lines[1:-1])
                return json.loads(text)

            except anthropic.RateLimitError as exc:
                last_exc = exc
                if attempt == _MAX_RETRIES:
                    break
                wait = _INITIAL_BACKOFF * (2 ** (attempt - 1))
                print(f"  Rate limited (attempt {attempt}/{_MAX_RETRIES}), waiting {wait}s...")
                time.sleep(wait)

            except (anthropic.APIStatusError, anthropic.APIConnectionError) as exc:
                last_exc = exc
                is_retryable = getattr(exc, "status_code", 0) in (500, 503)
                if not is_retryable or attempt == _MAX_RETRIES:
                    break
                wait = _INITIAL_BACKOFF * (2 ** (attempt - 1))
                print(f"  Retryable error (attempt {attempt}/{_MAX_RETRIES}), waiting {wait}s...")
                time.sleep(wait)

            except json.JSONDecodeError as exc:
                raise LLMError(f"Claude returned invalid JSON: {exc}") from exc

            except Exception as exc:
                raise LLMError(f"Claude API error: {exc}") from exc

        if isinstance(last_exc, anthropic.RateLimitError):
            raise LLMRateLimitError(
                f"Rate limited after {_MAX_RETRIES} retries: {last_exc}"
            ) from last_exc
        raise LLMError(f"Claude API error: {last_exc}") from last_exc

    # ------------------------------------------------------------------
    def chat(self, system_prompt: str, *, model: str | None = None) -> "ClaudeChat":
        """Start a multi-turn chat session.

        Args:
            system_prompt: System instruction for the conversation.
            model: Optional model override.

        Returns:
            A ClaudeChat instance.
        """
        model = model or self.default_model
        return ClaudeChat(self._client, system_prompt, model)


class ClaudeChat(ChatSession):
    """Multi-turn chat session backed by the Claude Messages API."""

    def __init__(self, client: anthropic.Anthropic, system_prompt: str, model: str) -> None:
        self._client = client
        self._system = system_prompt
        self._model = model
        self._history: list[dict] = []

    def send(self, message: str) -> str:
        """Send a message and return the model's text response."""
        self._history.append({"role": "user", "content": message})
        try:
            response = self._client.messages.create(
                model=self._model,
                max_tokens=_MAX_TOKENS,
                system=self._system,
                messages=self._history,
            )
            reply = response.content[0].text
            self._history.append({"role": "assistant", "content": reply})
            return reply
        except Exception as exc:
            raise LLMError(f"Claude chat error: {exc}") from exc
