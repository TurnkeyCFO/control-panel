# Control Panel Rule

**The Turnkey Control Panel is the single local ops dashboard. It binds to `127.0.0.1:7823` only, runs with zero auth but a hardened loopback layer, and controls skills/tasks exclusively through a hardcoded registry.** Any addition or change must obey the rules below.

## Why

The panel holds 40+ production keys (Stripe live, QBO, GitHub PATs, OpenRouter, Ramp, Supabase service key, Beehiiv, Blotato) and can trigger real automations (content posts, GitHub pushes, bill-pay). Loopback bind alone is insufficient — the rules below close the blast radius without adding a login surface Ricky has to maintain.

## How to apply

### Bind and network
- Bind must be literal `127.0.0.1` inside `uvicorn.run()` in `app/main.py`. Do not use CLI `--host` flags or env-driven hosts.
- Startup must abort if `UVICORN_HOST`, `HOST`, or `--host` appear in env / argv.
- `install_task.ps1` must add a Windows Firewall inbound-deny rule on TCP 7823.
- Never introduce `0.0.0.0` literals anywhere under `control-panel/`. Pre-commit grep enforces this.

### Adding a collector
- One file under `app/collectors/<name>.py` exporting `async def collect() -> list[dict]`.
- Secrets fetched via `secrets.get(...)` — caller whitelist only permits `app.collectors.*` and `app.controls.*`.
- Register in `app/collectors/__init__.py` with `(name, interval_seconds)`.
- Update the README's Data sources + collectors table.

### Adding a controllable skill
- One entry in `app/controls/registry.py` with explicit `argv`, `cwd`, `write_action`, and label.
- Free-form skill ids are forbidden anywhere in the route handlers.
- Set `write_action=True` for anything that posts / pushes / sends / charges — the UI then enforces the 30-second nonce re-click and fires a Slack ping to `SLACK_CHANNEL_ASSISTANTBOT`.

### Deny-list paths
- `skill_runner` must reject any write under `CLAUDE.md`, `.claude/CLAUDE.md`, `.claude/rules/`, or `context/`. Those changes route through `claude-maintenance` per `.claude/rules/maintenance.md`.

### URL and logs
- Canonical URL: `http://127.0.0.1:7823`.
- Persistent state lives in `%LOCALAPPDATA%\turnkey-cp\` with user-only ACL (enforced by `icacls` in `install_task.ps1`). Never under OneDrive-synced paths.

### Reminders channel
- All dashboard-originated pings (watchdog restarts, write-action approvals, anomaly alerts) go to Slack per `.claude/rules/reminders-channel.md`. No Telegram.

## Exceptions

None without explicit confirmation from Ricky. If a genuine cross-machine view is ever required, it gets built as a separate service with auth — it does not loosen the bind on this one.
