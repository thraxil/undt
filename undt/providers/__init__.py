"""Provider abstraction.

The contract is deliberately one method wide: given a frozen system prompt
and a per-request user message, return text. Everything above this layer
treats providers as interchangeable; everything below is free to use each
vendor's own SDK and idioms.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Protocol, runtime_checkable


class LLMError(RuntimeError):
    """The provider could not produce a completion."""


class Refusal(LLMError):
    """A safety classifier declined the request.

    Distinct from `LLMError` because it is not a fault: nothing is broken and
    retrying the same request will not help, so the caller should answer the
    visitor rather than report an outage.
    """

    def __init__(self, category: str | None, explanation: str | None = None) -> None:
        self.category = category or "unspecified"
        self.explanation = explanation
        super().__init__(f"refused (category: {self.category})")


@dataclass
class Completion:
    text: str
    model: str  # the model that actually served this, which may be a fallback


@runtime_checkable
class Provider(Protocol):
    name: str
    model: str

    def complete(self, *, system: str, user: str) -> Completion:
        """Return the model's output for this system/user pair."""
        ...


def from_env() -> Provider:
    """Build the provider named by `UNDT_PROVIDER` (default: anthropic)."""
    kind = os.environ.get("UNDT_PROVIDER", "anthropic").strip().lower()
    return build(kind)


def build(kind: str) -> Provider:
    if kind == "anthropic":
        from undt.providers.anthropic import AnthropicProvider

        return AnthropicProvider()

    if kind in {"openai", "openai-compatible", "compatible"}:
        from undt.providers.openai_compatible import OpenAICompatibleProvider

        return OpenAICompatibleProvider()

    if kind == "echo":
        from undt.providers.echo import EchoProvider

        return EchoProvider()

    raise LLMError(
        f"unknown provider {kind!r}; expected 'anthropic', 'openai', or 'echo'"
    )
