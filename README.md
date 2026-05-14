# Turnkey Control Panel

Local-first ops dashboard for every Turnkey automation. One URL, always-on, zero recurring cost, zero LLM tokens to operate. Shows API spend, job status, skill health, and `.env` hygiene — with one-click Start / Stop / Trigger for registered skills and schedules.

- **URL:** `http://127.0.0.1:7823`
- **Bind:** loopback only (hard-enforced)
- **Brand:** TK Services parent — light theme, black on white, Plus Jakarta Sans

## Purpose

| Question | Answer lives in |
|---|---|
| What am I spending across providers today / WTD / MTD? | Cost tiles |
| What jobs ran, failed, or are next? | Jobs & schedules table |
| What's running right now? | Live activity feed + Skills panel |
| Is my `.env` clean — any unused / stale keys? | Environment audit |
| Can I start / stop / trigger a skill without opening a terminal? | Yes — registered skills only, CSRF-gated |

## Quickstart

| Action | Command |
|---|---|
| Install | `pip install -r control-panel/requirements.txt` |
| First run (manual) | `control-panel/scripts/run.bat` |
| Register auto-start (logon + watchdog) | `powershell -ExecutionPolicy Bypass -File control-panel/scripts/install_task.ps1` |
| Open dashboard | `http://127.0.0.1:7823` |
| Stop (tray) | Right-click tray icon → Stop |
| Stop (task) | `schtasks /End /TN TurnkeyControlPanel` |
| Kill-switch (halts watchdog) | `type NUL > %LOCALAPPDATA%\turnkey-cp\kill-switch` |
| Logs | `%LOCALAPPDATA%\turnkey-cp\` (db, csrf, actions.log) |

## Architecture

FastAPI + SQLite + vanilla HTML/JS + vendored Chart.js, bound to `127.0.0.1:7823` via `uvicorn.run()` inside `main.py` (not CLI flags). Collectors poll APIs and filesystems on fixed intervals and write metadata-only rows to SQLite; a websocket pushes new rows to the single-page UI. Controls route through a hardcoded skill/task registry — no free-form names — with CSRF double-submit, Host/Origin allowlist, and a Slack-backed second-factor approval for write actions. Storage and CSRF token live in `%LOCALAPPDATA%\turnkey-cp\` with user-only ACL.

## Data sources + collectors

| Source | Collector | Frequency | Auth |
|---|---|---|---|
| OpenRouter credits + generation history | `openrouter.py` | 5 min | `OPENROUTER_MANAGEMENT_KEY` |
| Anthropic usage_report | `anthropic.py` | 1 hr | `ANTHROPIC_API_KEY` |
| OpenAI /v1/usage | `openai.py` | 1 hr | `OPENAI_ADMIN_KEY` |
| Blotato posts | `blotato.py` | 15 min | `BLOTATO_API_KEY` |
| Beehiiv sends | `beehiiv.py` | 1 hr | `TKCFO_BEEHIIV_API_KEY` |
| Firecrawl credits | `firecrawl.py` | 1 hr | `FIRECRAWL_API_KEY` |
| GitHub actions + rate-limit | `github.py` | 10 min | `GITHUB_PAT` |
| Skill state | `skills_state.py` | 1 min | filesystem |
| Task Scheduler | `task_scheduler.py` | 1 min | OS |
| Processes | `processes.py` | 15 s | psutil |
| .env audit | `env_audit.py` | 1 hr | filesystem (keys-only) |

Presence-only in v1 (no usage poll): Supabase, Slack, Telegram, Stripe, Ramp, QBO, Gusto, Azure, Google, Render, Instantly, Apify, Apollo, ClickUp, Windsor, Zapier, Stitch.

## Security model (summary)

- **Bind:** `127.0.0.1` hardcoded in `uvicorn.run()`; startup aborts if `UVICORN_HOST`, `HOST`, or `--host` appear in env/argv.
- **Firewall:** `install_task.ps1` adds an inbound-deny rule on TCP 7823 (defense-in-depth).
- **Host + Origin allowlist:** only `127.0.0.1:7823` / `localhost:7823`. Blocks DNS rebinding and cross-origin.
- **CSRF:** double-submit cookie + `X-TK-CP-CSRF` header on every state-changing route. Token in `%LOCALAPPDATA%\turnkey-cp\csrf`, user-only ACL.
- **CSP:** `default-src 'self'`; Chart.js vendored locally (no CDN).
- **WS origin check:** same allowlist; handshake rejected otherwise.
- **Registry-only control:** `controls/registry.py` hardcodes every runnable skill and task with explicit `argv`, `cwd`, `write_action`. No shell, no free-form names.
- **Write-action second factor:** post / push / send / charge actions require a 30-second nonce re-click + Slack ping to `SLACK_CHANNEL_ASSISTANTBOT`.
- **Deny-list paths:** `CLAUDE.md`, `.claude/rules/`, `.claude/CLAUDE.md`, `context/` — all writes rejected; those go through `claude-maintenance`.
- **Secrets never on the wire:** `/api/env` returns `{key, present, last4, provider, last_referenced_at}` only. Unit-tested against secret regex (`sk_live_`, `sk-`, `pat_`, `ghp_`, `xoxb-`).
- **`env_audit.py` is keys-only:** line-scanner captures only `KEY` left of `=`; values never read into any variable, never logged.
- **Just-in-time secret access:** `secrets.get(name)` introspects `inspect.stack()` and rejects callers outside `app.collectors.*` / `app.controls.*`.
- **Telemetry is metadata-only, schema-locked:** `llm_calls` columns frozen; pre-commit + runtime asserts block `prompt|response|body|content|messages`.
- **Model-routing enforced:** direct `api.anthropic.com` / `api.openai.com` calls outside `_openrouter.py` + collectors are rejected and logged.
- **Central redactor:** `app/util/redact.py` runs over every disk / WS string. FastAPI `debug=False`; clients receive `{"error":"internal"}`.
- **Audit log:** append-only `actions.log` JSONL records every Trigger/Start/Stop with `ts, route, skill_id, caller_origin, csrf_ok, outcome`.
- **Tray icon (not hidden):** `pystray` shows status + Stop; preferred over `pythonw`.
- **Reminders:** all dashboard-originated pings go to Slack per `.claude/rules/reminders-channel.md`.

## Adding a new collector

1. Create `app/collectors/<name>.py` exporting `async def collect() -> list[dict]`.
2. Return rows matching an existing SQLite table, or add a migration in `app/db.py` (bump schema version).
3. Register in `app/collectors/__init__.py` with a `(name, interval_seconds)` tuple.
4. If the collector needs a secret, read it via `secrets.get("ENV_KEY_NAME")` — the caller-whitelist only permits `app.collectors.*`.
5. Add the row to the **Data sources + collectors** table in this README.
6. Run once manually: `python -m app.collectors.<name>` → verify rows land in SQLite and no secrets appear in `actions.log`.

## Adding a new controllable skill

1. Add a `SkillSpec` entry to `app/controls/registry.py`:
   ```python
   SKILLS["my_skill"] = SkillSpec(
       argv=["python", "-m", "skill_package.entry"],
       cwd=r"C:\Users\ricky_j3cdbqw\CLAUDE CODE PROJECTS\...",
       write_action=False,  # True if it posts/pushes/sends/charges
       label="My Skill",
   )
   ```
2. If `write_action=True`, the UI automatically requires the 30-second nonce re-click and fires a Slack ping.
3. Never accept a free-form skill id in any route — `skill_runner.run()` only dispatches from this registry.
4. Confirm the skill's writes respect the deny-list (`CLAUDE.md`, `.claude/rules/`, `context/`). Hygiene changes must route through `claude-maintenance`.
5. Reload the dashboard — the skill appears in the Skills panel.

## Troubleshooting

| Symptom | Check |
|---|---|
| Dashboard won't load | Is the task running? `schtasks /Query /TN TurnkeyControlPanel` |
| Process keeps dying | Watchdog log: `%LOCALAPPDATA%\turnkey-cp\watchdog.log`; Slack ping at >3 restarts/hr |
| Want to stop the watchdog | `type NUL > %LOCALAPPDATA%\turnkey-cp\kill-switch` |
| LAN device reached `:7823` | That's the bug. Check `main.py` bind + firewall rule + startup assertion |
| "CSRF token mismatch" | Clear `%LOCALAPPDATA%\turnkey-cp\csrf`, hard-refresh page |
| Collector silent | `actions.log` + per-collector stderr in `%LOCALAPPDATA%\turnkey-cp\collectors\<name>.log` |
| Secret leaked in a response | Bug — file an ERROR via `self-improvement` rule, rotate the key, patch the redactor |
| `.env` key shows unreferenced but is in use | Grep scope in `env_audit.py` may miss dynamic refs — add the path |

**Logs location:** `%LOCALAPPDATA%\turnkey-cp\`
- `control-panel.db` — SQLite
- `csrf` — CSRF token (user-only ACL)
- `actions.log` — append-only JSONL audit
- `watchdog.log` — restart events
- `collectors/*.log` — per-collector stderr

## Roadmap (v1.1)

| Item | Why |
|---|---|
| DPAPI-wrap `.env` at rest (`win32crypt.CryptProtectData`) | Defense-in-depth if `.env` leaves the machine |
| SQLite at-rest encryption (SQLCipher or app-level) | Metadata is low-sensitivity but exposure surface still matters |
| Subprocess isolation for collectors (per-collector user / AppContainer) | Blast radius if any collector is compromised |
| Targeted usage collectors for Stripe MRR + Supabase row counts | Highest-signal metrics missing in v1 |
| Export / anomaly alerts (daily spend > rolling mean + 2σ → Slack) | Catch runaway automations early |

## Control Center / Executive Assistant Layer

The Control Center tab adds a day/week command-center layer on top of the existing analytics panels. It is intentionally read-only for external systems in v1.

What it shows:
- Morning Brief first draft
- Needs Ricky / Today / This Week
- Notes & Actions capture
- Action Radar
- Brain/source health, including explicit unavailable-source notices

Run a local first-draft digest:

```bash
python scripts/control_center_digest.py
```

The digest writes markdown artifacts to:

```text
artifacts/control-center/
```

Local smoke check:

```bash
python -m py_compile app/db.py app/main.py app/collectors/control_center.py scripts/control_center_digest.py
python - <<'PY'
from app.db import init_db
init_db()
from app.collectors import control_center
summary = control_center.summary(refresh=True)
print(summary['brief'].splitlines()[0])
PY
```

Current v1 source behavior:
- Obsidian brain: reads wiki log/index signals.
- Claude Code: uses the existing Claude Code collector when available.
- Slack/email/calendar: surfaced as unavailable until read credentials are explicitly configured for the control-panel app.
- Client dashboards: remain command-only and are not included in recurring daily loops.

