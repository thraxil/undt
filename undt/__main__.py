"""`python -m undt` — run the development server."""

from __future__ import annotations

import argparse
import logging
import os

from undt.app import create_app
from undt.providers import build


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="undt",
        description="Serve an application that has no implementation.",
    )
    parser.add_argument(
        "app_file",
        nargs="?",
        default=os.environ.get("UNDT_APP_FILE", "app.md"),
        help="markdown description of the application (default: app.md)",
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5000)
    parser.add_argument(
        "--provider",
        default=os.environ.get("UNDT_PROVIDER", "anthropic"),
        help="anthropic, openai, or echo",
    )
    parser.add_argument(
        "--debug-headers",
        action="store_true",
        help="add X-Undt-* headers with provider, timing and the model's private note",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    app = create_app(
        app_file=args.app_file,
        provider=build(args.provider),
        debug_headers=args.debug_headers,
    )
    # Threaded so a slow completion doesn't block the page's subresources.
    app.run(host=args.host, port=args.port, threaded=True)


if __name__ == "__main__":
    main()
