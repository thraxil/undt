"""A provider that never calls anything.

Useful for exercising the request serialisation, the response parser and the
session store without spending tokens: it returns a valid response spec whose
body is the prompt it was handed.
"""

from __future__ import annotations

import html
import json

from undt.providers import Completion


class EchoProvider:
    name = "echo"
    model = "echo"

    def complete(self, *, system: str, user: str) -> Completion:
        body = (
            "<!doctype html><html><head><title>echo</title></head><body>"
            "<h1>echo provider</h1>"
            "<h2>system prompt</h2><pre>"
            f"{html.escape(system)}"
            "</pre><h2>user message</h2><pre>"
            f"{html.escape(user)}"
            "</pre></body></html>"
        )
        return Completion(
            text=json.dumps(
                {
                    "status": 200,
                    "content_type": "text/html; charset=utf-8",
                    "body": body,
                    "note": "echoed the prompt back",
                }
            ),
            model=self.model,
        )
