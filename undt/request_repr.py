"""Serialise an incoming HTTP request into a plain JSON-able dict.

This is the only thing the model is told about what the client wants, so it
aims to be complete and literal: no interpretation, no normalisation beyond
what is needed to survive `json.dumps`.
"""

from __future__ import annotations

import base64
from typing import Any

from flask import Request

MAX_BODY_BYTES = 64 * 1024


def serialize_request(request: Request, *, max_body: int = MAX_BODY_BYTES) -> dict[str, Any]:
    raw = request.get_data(cache=True)
    truncated = len(raw) > max_body
    if truncated:
        raw = raw[:max_body]

    body: dict[str, Any] = {"length": request.content_length or len(raw)}
    if not raw:
        body["encoding"] = "empty"
    else:
        try:
            body["encoding"] = "text"
            body["text"] = raw.decode("utf-8")
        except UnicodeDecodeError:
            body["encoding"] = "base64"
            body["base64"] = base64.b64encode(raw).decode("ascii")
    if truncated:
        body["truncated"] = True

    payload: dict[str, Any] = {
        "method": request.method,
        "path": request.path,
        "full_path": request.full_path,
        "scheme": request.scheme,
        "host": request.host,
        "url": request.url,
        "query": _multi(request.args),
        "headers": _multi(request.headers),
        "cookies": dict(request.cookies),
        "remote_addr": request.remote_addr,
        "content_type": request.content_type,
        "body": body,
    }

    # Werkzeug only populates these for form-ish content types; when it does,
    # the parsed view is far more useful to the model than the raw body.
    if request.form:
        payload["form"] = _multi(request.form)
    if request.files:
        payload["files"] = [
            {
                "field": name,
                "filename": storage.filename,
                "content_type": storage.content_type,
            }
            for name, storage in request.files.items(multi=True)
        ]

    return payload


def _multi(mapping: Any) -> dict[str, Any]:
    """Collapse a multidict to `{key: value}`, or `{key: [values]}` on repeats."""
    out: dict[str, Any] = {}
    for key in mapping.keys():
        values = mapping.getlist(key)
        out[key] = values[0] if len(values) == 1 else values
    return out
