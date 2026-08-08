"""Any server that speaks the OpenAI chat-completions wire format.

Covers OpenAI itself plus Ollama, vLLM, Groq, Together, OpenRouter and the
rest, by pointing `UNDT_BASE_URL` at them. Raw HTTP rather than an SDK keeps
the dependency list to httpx.
"""

from __future__ import annotations

import os

import httpx

from undt.providers import Completion, LLMError

DEFAULT_BASE_URL = "https://api.openai.com/v1"
DEFAULT_MODEL = "gpt-4o"
DEFAULT_MAX_TOKENS = 16000
DEFAULT_TIMEOUT = 180.0


class OpenAICompatibleProvider:
    name = "openai-compatible"

    def __init__(
        self,
        model: str | None = None,
        *,
        base_url: str | None = None,
        api_key: str | None = None,
        max_tokens: int | None = None,
        timeout: float | None = None,
    ) -> None:
        self.model = model or os.environ.get("UNDT_MODEL") or DEFAULT_MODEL
        self._base_url = (
            base_url or os.environ.get("UNDT_BASE_URL") or DEFAULT_BASE_URL
        ).rstrip("/")
        self._api_key = (
            api_key
            or os.environ.get("UNDT_API_KEY")
            or os.environ.get("OPENAI_API_KEY")
            or ""
        )
        self._max_tokens = max_tokens or int(
            os.environ.get("UNDT_MAX_TOKENS") or DEFAULT_MAX_TOKENS
        )
        self._client = httpx.Client(
            timeout=timeout or float(os.environ.get("UNDT_TIMEOUT") or DEFAULT_TIMEOUT)
        )

    def complete(self, *, system: str, user: str) -> Completion:
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        try:
            response = self._client.post(
                f"{self._base_url}/chat/completions",
                headers=headers,
                json={
                    "model": self.model,
                    "max_tokens": self._max_tokens,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                },
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            body = exc.response.text[:500]
            raise LLMError(f"{exc.response.status_code} from provider: {body}") from exc
        except httpx.HTTPError as exc:
            raise LLMError(f"provider request failed: {exc}") from exc

        try:
            payload = response.json()
            text = payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise LLMError(f"unexpected completion payload: {exc}") from exc

        if not text or not text.strip():
            raise LLMError("empty completion")
        return Completion(text=text, model=payload.get("model") or self.model)
