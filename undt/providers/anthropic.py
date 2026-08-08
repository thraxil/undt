"""Claude, via the official Anthropic SDK."""

from __future__ import annotations

import os

from undt.providers import Completion, LLMError, Refusal

DEFAULT_MODEL = "claude-opus-5"
DEFAULT_EFFORT = "low"
DEFAULT_MAX_TOKENS = 16000
DEFAULT_FALLBACK = "default"


class AnthropicProvider:
    name = "anthropic"

    def __init__(
        self,
        model: str | None = None,
        *,
        effort: str | None = None,
        max_tokens: int | None = None,
        fallback: str | None = None,
    ) -> None:
        try:
            import anthropic
        except ImportError as exc:  # pragma: no cover - import guard
            raise LLMError(
                "the anthropic package is not installed; "
                "install it with `uv sync --extra anthropic`"
            ) from exc

        self._sdk = anthropic
        # Credentials resolve from the environment: ANTHROPIC_API_KEY,
        # ANTHROPIC_AUTH_TOKEN, or an `ant auth login` profile.
        self._client = anthropic.Anthropic()
        self.model = model or os.environ.get("UNDT_MODEL") or DEFAULT_MODEL
        # A page request is a latency path, so effort is low by default;
        # raise it if the application description is intricate.
        self._effort = effort or os.environ.get("UNDT_EFFORT") or DEFAULT_EFFORT
        self._max_tokens = max_tokens or int(
            os.environ.get("UNDT_MAX_TOKENS") or DEFAULT_MAX_TOKENS
        )
        self._fallbacks, self._betas = _fallback_config(
            fallback or os.environ.get("UNDT_FALLBACK") or DEFAULT_FALLBACK
        )

    def complete(self, *, system: str, user: str) -> Completion:
        request = {
            "model": self.model,
            "max_tokens": self._max_tokens,
            "output_config": {"effort": self._effort},
            "system": [
                {
                    "type": "text",
                    "text": system,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            "messages": [{"role": "user", "content": user}],
        }

        try:
            if self._fallbacks is None:
                response = self._client.messages.create(**request)
            else:
                # Fallbacks live on the beta endpoint. A request the primary
                # model declines is re-served by the fallback inside this same
                # call, so a false-positive classifier hit costs latency
                # rather than an error.
                response = self._client.beta.messages.create(
                    **request, fallbacks=self._fallbacks, betas=self._betas
                )
        except self._sdk.APIError as exc:
            raise LLMError(f"anthropic request failed: {exc}") from exc

        if response.stop_reason == "refusal":
            # With fallbacks configured this means the whole chain declined.
            details = getattr(response, "stop_details", None)
            raise Refusal(
                getattr(details, "category", None),
                getattr(details, "explanation", None),
            )

        text = "".join(
            block.text for block in response.content if block.type == "text"
        )
        if not text.strip():
            raise LLMError(f"empty completion (stop_reason: {response.stop_reason})")
        return Completion(text=text, model=response.model)


def _fallback_config(setting: str) -> tuple[object | None, list[str]]:
    """Resolve `UNDT_FALLBACK` into a `fallbacks` value and its beta header.

    The two request shapes are gated by different beta headers and pairing
    one with the other is a 400, so they are chosen together here.
    """
    setting = setting.strip()

    if setting.lower() in {"off", "none", "no", ""}:
        # Bedrock, Vertex and Foundry reject the parameter outright.
        return None, []

    if setting.lower() == "default":
        # Anthropic picks the substitute by refusal category — cyber-category
        # refusals route to Opus 4.8 — so there is no model list to maintain.
        return "default", ["server-side-fallback-2026-07-01"]

    return [{"model": setting}], ["server-side-fallback-2026-06-01"]
