# undt

A Flask application with one route and no implementation.

Every request, any method, any path, is serialised to JSON, handed to a
language model along with a markdown description of what the application is
supposed to be, and the model's answer is turned back into an HTTP response.
There are no views, no templates, no database. The site is improvised on
arrival and forgotten when the process exits.

```
GET /object/UND-1913-0447
        │
        ▼
  serialize_request()          →  {"method": "GET", "path": "...", "headers": {...}}
        │
        ▼
  app.md + protocol            →  system prompt (frozen, cacheable)
  request + history + memory   →  user message
        │
        ▼
  provider.complete()
        │
        ▼
  parse_response()             →  {"status": 200, "body": "<!doctype html>...", "memory": [...]}
        │
        ▼
  200 text/html
```

## Running it

```sh
uv sync --extra anthropic
export ANTHROPIC_API_KEY=...
uv run undt app.md --debug-headers
```

Then open <http://127.0.0.1:5000/>. Follow the links. Type a path that
doesn't exist and see what the model decides is there.

To check the plumbing without spending anything, the `echo` provider returns
the prompt it was given as an HTML page:

```sh
uv run undt app.md --provider echo
```

## Writing the application

`app.md` is the whole specification. It is passed through verbatim after a
protocol preamble, so anything you can describe in prose is a feature: the
voice, the URL scheme, the status codes, the visual style, which paths are
JSON and which are HTML. Point at a different file to run a different site:

```sh
uv run undt sites/bookshop.md
```

The description in this repo is a catalogue of objects that were never
built. It is a starting point, not a fixture — replace it.

## Providers

`Provider` is a one-method protocol (`complete(system=, user=) -> str`), so
adding a vendor is a file in `undt/providers/`.

| `--provider` | Backend | Configure with |
|---|---|---|
| `anthropic` (default) | Claude, via the official `anthropic` SDK | `ANTHROPIC_API_KEY`, `UNDT_MODEL` (default `claude-opus-5`), `UNDT_EFFORT` (default `low`), `UNDT_FALLBACK` (default `default`) |
| `openai` | Anything speaking OpenAI chat-completions — OpenAI, Ollama, vLLM, Groq, OpenRouter | `UNDT_BASE_URL`, `UNDT_API_KEY`, `UNDT_MODEL` |
| `echo` | Nothing. Returns the prompt. (for testing) | — |

Other environment variables: `UNDT_APP_FILE`, `UNDT_MAX_TOKENS`,
`UNDT_TIMEOUT`, `UNDT_DEBUG`.

## Continuity

A stateless model serving a stateless protocol produces a site that
contradicts itself on the second click, so each visitor gets a cookie and,
behind it, two things:

- **history** — the last dozen exchanges, as one line each
- **memory** — notes the model chooses to write for itself in the `memory`
  field of its response, carried forward for the rest of the session

Both live in memory and are bounded (`undt/history.py`). Restarting the
server wipes the world. This is a feature, but swapping `SessionStore` for
something durable is a small change if you disagree.

## The response protocol

The model is asked for a single JSON object:

```json
{
  "status": 200,
  "content_type": "text/html; charset=utf-8",
  "headers": {"X-Anything": "optional"},
  "body": "<!doctype html>...",
  "body_encoding": "text",
  "memory": ["UND-1913-0447 is a brass hinge, filed 1913"],
  "note": "served the object record"
}
```

`body_encoding: "base64"` returns binary. A `body` given as a nested object
is serialised as JSON. `Content-Length` and other hop-by-hop headers are
stripped and recomputed. Fenced or preamble-wrapped JSON is recovered rather
than rejected — see `undt/response_spec.py`.

When the provider fails or returns something unparseable, the client gets a
`502` in plain text; the model's failure is never disguised as a page.

## Refusals

Serving arbitrary HTTP requests to a frontier model means occasionally
tripping a safety classifier. The usual cause is not your `app.md` — it is
the request itself. Anything crawling your server sends probe paths
(`/.env`, `/wp-login.php`, traversal in a query string) and undt forwards
them to the model verbatim, which looks cyber-adjacent to a classifier even
though nothing here is exploiting anything.

Two things handle it:

- **Fallbacks are on by default.** `UNDT_FALLBACK=default` sends the
  server-side `fallbacks` parameter, so a request Opus 5 declines is
  re-served by Opus 4.8 inside the same call. It costs latency, not an
  error. Set `UNDT_FALLBACK=claude-opus-4-8` to name the substitute
  yourself, or `UNDT_FALLBACK=off` on Bedrock, Vertex and Foundry, which
  reject the parameter.
- **A full refusal renders a bare `404`,** not a `502`. If the whole chain
  declines there is no model left to write an in-character page, and a
  gateway error would announce the mechanism to whoever is probing you. The
  refusal and its category go to the log instead.

Run with `--debug-headers` to watch this: `X-Undt-Model` reports the model
that actually answered, so it reads `claude-opus-4-8` on a request that fell
back and `claude-opus-5` otherwise.

If a fallback is still too slow for you and the traffic is bots rather than
visitors, the cheapest fix is to short-circuit obvious probe paths to a
static `404` in `improvise()` before the provider is called — that also
stops you paying tokens for scanners. It is deliberately not the default,
because a made-up page for `/.env` is arguably the best thing this
application does.

## Layout

| File | |
|---|---|
| `undt/app.py` | the catch-all route |
| `undt/request_repr.py` | HTTP request → dict |
| `undt/prompt.py` | the protocol preamble and message assembly |
| `undt/response_spec.py` | model output → HTTP response |
| `undt/history.py` | per-visitor history and memory |
| `undt/providers/` | one file per backend |
| `app.md` | the application |
