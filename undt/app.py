"""The whole application: one route, one model, no plan."""

from __future__ import annotations

import logging
import os
import secrets
import time
from pathlib import Path

from flask import Flask, Response, request

from undt.history import Exchange, SessionStore
from undt.prompt import build_system_prompt, build_user_message
from undt.providers import LLMError, Provider, Refusal, from_env
from undt.request_repr import serialize_request
from undt.response_spec import MalformedResponse, ResponseSpec, parse_response

log = logging.getLogger("undt")

METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"]
SESSION_COOKIE = "undt_session"
DEFAULT_APP_FILE = "app.md"


def create_app(
    *,
    app_file: str | os.PathLike[str] | None = None,
    provider: Provider | None = None,
    debug_headers: bool | None = None,
) -> Flask:
    app = Flask(__name__)

    path = Path(app_file or os.environ.get("UNDT_APP_FILE") or DEFAULT_APP_FILE)
    if not path.is_file():
        raise FileNotFoundError(
            f"no application description at {path}; "
            "point UNDT_APP_FILE at a markdown file"
        )
    system_prompt = build_system_prompt(path.read_text(encoding="utf-8"))

    llm = provider or from_env()
    sessions = SessionStore()
    show_debug = (
        debug_headers
        if debug_headers is not None
        else os.environ.get("UNDT_DEBUG", "").lower() in {"1", "true", "yes"}
    )

    log.info("undt serving %s via %s (%s)", path, llm.name, llm.model)

    @app.route("/", defaults={"path": ""}, methods=METHODS)
    @app.route("/<path:path>", methods=METHODS)
    def improvise(path: str) -> Response:  # noqa: ARG001 - path is in `request`
        started = time.monotonic()
        session_id = request.cookies.get(SESSION_COOKIE) or secrets.token_urlsafe(12)
        is_new_session = SESSION_COOKIE not in request.cookies

        serialized = serialize_request(request)
        history, memory = sessions.snapshot(session_id)
        user_message = build_user_message(serialized, history, memory)

        try:
            completion = llm.complete(system=system_prompt, user=user_message)
        except Refusal as exc:
            # A safety classifier declined the request — most often because a
            # scanner's payload is sitting in the path or query string. That
            # is not an outage, and saying so would break the fiction, so the
            # visitor gets the answer such a request usually deserves.
            log.warning(
                "%s %s refused (category: %s)",
                request.method,
                request.full_path,
                exc.category,
            )
            return _not_found()
        except LLMError as exc:
            log.warning("%s %s: %s", request.method, request.full_path, exc)
            return _gateway_error(f"The application could not be reached.\n\n{exc}", 502)

        try:
            spec = parse_response(completion.text)
        except MalformedResponse as exc:
            log.warning("unparseable completion for %s: %s", request.full_path, exc)
            return _gateway_error(
                f"The application returned something incomprehensible.\n\n{exc}", 502
            )

        sessions.record(
            session_id,
            Exchange(
                method=request.method,
                path=request.full_path,
                response=spec.summary(),
                note=spec.note,
            ),
            spec.memory,
        )

        response = _to_response(spec)
        if is_new_session:
            response.set_cookie(
                SESSION_COOKIE, session_id, httponly=True, samesite="Lax"
            )
        if show_debug:
            response.headers["X-Undt-Provider"] = llm.name
            # Differs from the configured model when a fallback served it.
            response.headers["X-Undt-Model"] = completion.model
            response.headers["X-Undt-Elapsed"] = f"{time.monotonic() - started:.2f}s"
            if spec.note:
                response.headers["X-Undt-Note"] = spec.note[:200].replace("\n", " ")
        return response

    return app


def _to_response(spec: ResponseSpec) -> Response:
    response = Response(spec.body, status=spec.status)
    # Replace rather than extend: Flask has already guessed a content type.
    for key, value in spec.headers.items():
        response.headers[key] = value
    return response


def _gateway_error(message: str, status: int) -> Response:
    return Response(message, status=status, mimetype="text/plain; charset=utf-8")


def _not_found() -> Response:
    """The one page undt serves without asking the model."""
    return Response(
        "<!doctype html><html><head><title>Not Found</title></head>"
        "<body><h1>Not Found</h1></body></html>",
        status=404,
        mimetype="text/html; charset=utf-8",
    )
