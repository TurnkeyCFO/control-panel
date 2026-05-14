# LLM Telemetry Rule

**Every LLM call site in this workspace MUST route through `shared/llm_telemetry/record.py`. The wrapper logs metadata only, with a frozen column set; prompt and response bodies are forbidden on disk, wire, or log.**

## Why

The control panel's per-skill cost attribution, anomaly detection, and `.env` audit all depend on a single telemetry choke point. Equally important: the wrapper is how we guarantee no prompt / response content ever lands in SQLite, logs, or the dashboard's websocket — regardless of which skill author wrote the call site.

## How to apply

### Required at every call site
- Import and wrap via `shared/llm_telemetry/record.py`. Direct `httpx.post` to `openrouter.ai`, `api.anthropic.com`, or `api.openai.com` is forbidden outside the wrapper and the control-panel collectors.
- Model-routing per `model-routing` skill still applies — every call goes through OpenRouter.
- Pass an `X-TK-Skill` header naming the calling skill (e.g. `tkcfo-content-engine`, `faithful-content-engine`, `morning-brief`). Header is a **label only** — never used for authZ or rate-limits. Collectors cross-check the PID via psutil and flag mismatches.

### Frozen schema
The `llm_calls` SQLite table has exactly these columns and no others:
```
ts, provider, model, skill_tag, tokens_in, tokens_out, usd, latency_ms, status, pid
```
- Schema changes require rotating `FROZEN_COLS_VERSION` in `record.py` and a diff review.
- Runtime assert: `assert set(row.keys()) <= FROZEN_COLS` before every INSERT.

### Forbidden fields
Columns or log keys named `prompt`, `response`, `body`, `content`, `messages`, `completion`, `headers` are banned. Pre-commit grep fails the build on any match under `shared/llm_telemetry/`, `control-panel/`, or any skill's telemetry adapter.

### Enforcement
- Pre-commit hook: regex scan for direct provider-host POSTs + banned column names.
- Runtime guard: `record.py` raises on unknown columns.
- Control-panel collector validates that every skill with non-zero cost in a 24-hour window emitted at least one `X-TK-Skill`-tagged row; missing skills surface in the dashboard as "attribution gap."

### Redaction
- Any exception path that could log a request body must route through `app/util/redact.py` (control-panel) or the equivalent shared redactor. FastAPI runs with `debug=False` and returns `{"error":"internal"}` to clients.

## Exceptions

None. If a skill truly needs to log prompt/response for debugging, it writes to a local, git-ignored, machine-only file under `%LOCALAPPDATA%\turnkey-cp\debug\<skill>\` — not into `llm_calls`, not into `actions.log`, not into any response payload. Debug dumps are opt-in per-session and cleaned up on restart.
