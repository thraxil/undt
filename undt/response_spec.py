"""Turn whatever the model said into something Flask can send back."""

from __future__ import annotations

import base64
import binascii
import json
import re
from dataclasses import dataclass, field
from typing import Any

_FENCE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)

MAX_MEMORY_NOTE_CHARS = 400


class MalformedResponse(ValueError):
    """The model returned something that is not a usable response spec."""


@dataclass
class ResponseSpec:
    status: int = 200
    headers: dict[str, str] = field(default_factory=dict)
    body: bytes = b""
    memory: list[str] = field(default_factory=list)
    note: str | None = None

    def summary(self) -> str:
        """A one-line description of this response, for the history log."""
        kind = self.headers.get("Content-Type", "")
        return f"{self.status} {kind} ({len(self.body)} bytes)"


def parse_response(text: str) -> ResponseSpec:
    """Parse the model's output into a `ResponseSpec`.

    Models are asked for bare JSON but reliably wrap it in prose or fences
    now and then, so this digs the object out rather than insisting.
    """
    data = _extract_json(text)

    if not isinstance(data, dict):
        raise MalformedResponse(f"expected a JSON object, got {type(data).__name__}")

    status = data.get("status", 200)
    if not isinstance(status, int) or not 100 <= status <= 599:
        raise MalformedResponse(f"bad status: {status!r}")

    headers = _headers(data)
    body = _body(data)

    memory = [
        str(item)[:MAX_MEMORY_NOTE_CHARS]
        for item in data.get("memory") or []
        if isinstance(item, (str, int, float))
    ]

    return ResponseSpec(
        status=status,
        headers=headers,
        body=body,
        memory=memory,
        note=data.get("note") if isinstance(data.get("note"), str) else None,
    )


def _extract_json(text: str) -> Any:
    candidates = [text.strip()]

    fenced = _FENCE.search(text)
    if fenced:
        candidates.insert(0, fenced.group(1))

    # Last resort: the outermost brace pair, for when the model prefaces the
    # object with a sentence of commentary.
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        candidates.append(text[start : end + 1])

    for candidate in candidates:
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue

    raise MalformedResponse("no JSON object found in model output")


def _headers(data: dict[str, Any]) -> dict[str, str]:
    headers: dict[str, str] = {}

    raw = data.get("headers")
    if isinstance(raw, dict):
        for key, value in raw.items():
            if isinstance(value, (str, int, float)):
                headers[str(key)] = str(value)

    # `content_type` is a shorthand the prompt offers; it wins over a header
    # of the same name only if the header is absent.
    content_type = data.get("content_type")
    if isinstance(content_type, str) and not _get(headers, "content-type"):
        headers["Content-Type"] = content_type

    if not _get(headers, "content-type"):
        headers["Content-Type"] = "text/html; charset=utf-8"

    # Length and encoding are ours to decide once the body is materialised.
    for hop_by_hop in ("content-length", "transfer-encoding", "connection"):
        for key in [k for k in headers if k.lower() == hop_by_hop]:
            del headers[key]

    return headers


def _body(data: dict[str, Any]) -> bytes:
    body = data.get("body", "")
    encoding = data.get("body_encoding", "text")

    if body is None:
        return b""

    if encoding == "base64":
        if not isinstance(body, str):
            raise MalformedResponse("base64 body must be a string")
        try:
            return base64.b64decode(body, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise MalformedResponse(f"undecodable base64 body: {exc}") from exc

    if isinstance(body, (dict, list)):
        # The model returned a JSON body inline rather than as a string.
        return json.dumps(body, indent=2).encode("utf-8")

    return str(body).encode("utf-8")


def _get(headers: dict[str, str], name: str) -> str | None:
    for key, value in headers.items():
        if key.lower() == name:
            return value
    return None
