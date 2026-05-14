# Control Center Implementation Plan

> **For Hermes/Claude Code:** Build this task-by-task. Keep source-of-truth boundaries read-only unless the owning skill/API explicitly writes. No Slack/Gmail/CRM/QBO writes in v1.

**Goal:** Replace the morning brief with a persistent Turnkey Control Center that surfaces Ricky's outstanding action items and maintains the second brain.

**Architecture:** Extend the existing FastAPI + SQLite + vanilla JS `control-panel/` app with an `action_items` layer, source collectors, a nightly aggregate job, and biweekly brain lint. The dashboard stays local-first at `127.0.0.1:7823`; Slack delivery goes to `#cortana` only. Claude Code dashboards remain command-only/ad hoc, not part of the daily loop.

**Tech Stack:** FastAPI, SQLite, vanilla JS, Hermes cron, existing Claude Code session logs, Gmail/Calendar via Google Workspace tooling, Slack where available, Obsidian wiki markdown.

---

## Scope decisions from Ricky — 2026-05-14

| Decision | Outcome |
|---|---|
| First priority | Develop Control Center, not client dashboards |
| Morning brief | Replace with Control Center once built |
| Client dashboards | Command-only/ad hoc when Ricky asks |
| Nightly job | Run around 1 AM, aggregate the day's Claude conversations, email, Slack, and owned-system activity |
| Brain maintenance | Maintain growth continuously; run lint every couple weeks |
| Output style | Enough detail to act, not a noisy dump |

## v1 acceptance criteria

1. Dashboard has a new **Action Radar / Control Center** tab.
2. `/api/control-center/summary` returns grouped pending items with source, owner, priority, evidence, and recommended next action.
3. Nightly 1 AM Hermes cron posts a concise digest to `#cortana` and saves a markdown archive.
4. Claude Code activity is scanned from session logs and summarized as "what happened / what remains open" without storing raw prompts/responses in the dashboard DB.
5. Email/Slack unavailable states are explicit, not silently omitted.
6. Wiki maintenance job runs biweekly and produces a lint report with stale pages, contradictions, missing links, and suggested ingests.
7. Morning brief is not deleted until Control Center digest has run successfully for several days.

## Data model

Add to `control-panel/app/db.py`:

```sql
CREATE TABLE IF NOT EXISTS action_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts REAL NOT NULL,
    source TEXT NOT NULL,
    source_ref TEXT,
    title TEXT NOT NULL,
    detail TEXT,
    priority TEXT NOT NULL DEFAULT 'normal',
    owner TEXT DEFAULT 'ricky',
    status TEXT NOT NULL DEFAULT 'open',
    recommended_action TEXT,
    evidence_path TEXT,
    expires_at REAL,
    UNIQUE(source, source_ref, title)
);
CREATE INDEX IF NOT EXISTS idx_action_items_status ON action_items(status, priority, ts DESC);

CREATE TABLE IF NOT EXISTS control_center_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts REAL NOT NULL,
    run_type TEXT NOT NULL,
    status TEXT NOT NULL,
    summary_path TEXT,
    notes TEXT
);
```

## Source collectors

| Collector | v1 method | Notes / guardrails |
|---|---|---|
| Claude Code | Existing `app/collectors/claude_code.py` session-log scan plus a separate summarizer script | Keep usage metadata in DB; write summaries to markdown archive, not raw prompts in DB |
| Email | Google Workspace/Gmail read-only query | Needs-reply, invoices, client asks, partner follow-ups; no sending |
| Slack | If Slack API token available, read allowed channels; otherwise mark unavailable | Do not post outside `#cortana`; no channel management |
| Calendar | Google Calendar read-only | Today/tomorrow commitments and prep needed |
| CRM | Existing CRM snapshot/read-only owner path | No direct writes to CRM Sheet |
| Lead-gen | Existing read-only `lead_gen` collector | Hot leads, failed jobs, overdue follow-ups |
| Wiki | Read `wiki/log.md`, `index.md`, and lint output | No raw edits except approved ingest/lint workflows |

## Output contract

Digest format:

```text
*Turnkey Control Center — YYYY-MM-DD*

*Needs Ricky today* (max 5)
1. [priority] Title — why it matters
   → Next action: ...
   Evidence: source/ref

*Watchlist* (max 5)
- ...

*Done / moved yesterday* (max 5)
- ...

*Unavailable sources*
- Slack: token missing / API unavailable / no access
```

Dashboard tab groups:

- Needs Ricky
- Client Delivery
- Revenue / Pipeline
- Ops / Systems
- Brain Maintenance
- Unavailable Sources

---

## Task 1: Add action-item tables

**Objective:** Persist normalized pending items and run history.

**Files:**
- Modify: `control-panel/app/db.py`

**Steps:**
1. Add `action_items` and `control_center_runs` DDL to `SCHEMA`.
2. Add helpers: `upsert_action_item(row)`, `open_action_items(limit=100)`, `record_control_center_run(...)`.
3. Run a Python import smoke test from `control-panel/`.

**Verify:**
```bash
cd control-panel
python - <<'PY'
from app.db import init_db, open_action_items
init_db()
print(open_action_items())
PY
```

## Task 2: Create control-center collector module

**Objective:** Provide one aggregation surface for all sources.

**Files:**
- Create: `control-panel/app/collectors/control_center.py`

**Steps:**
1. Implement `summary()` returning `{items, unavailable, generated_at}`.
2. Pull open items from DB.
3. Add placeholder source-status checks for email/slack/calendar until credentials are verified.
4. Never throw the whole summary on one source failure; append to `unavailable`.

## Task 3: Add API endpoints

**Objective:** Expose Control Center data to the UI and nightly job.

**Files:**
- Modify: `control-panel/app/main.py`

**Endpoints:**
- `GET /api/control-center/summary`
- `POST /api/control-center/refresh`

**Verify:**
```bash
curl http://127.0.0.1:7823/api/control-center/summary
```

## Task 4: Add Action Radar UI tab

**Objective:** Make the Control Center visible in the dashboard.

**Files:**
- Modify: `control-panel/web/index.html`
- Modify: `control-panel/web/app.js`
- Modify if needed: `control-panel/web/style.css`

**Steps:**
1. Add `<button class="tab" data-tab="control-center">Control Center</button>` near Overview.
2. Add a `data-panel="control-center"` section with grouped cards/tables.
3. Implement `loadControlCenter()` in `app.js`.
4. Wire tab switch to call it.

## Task 5: Build nightly digest script

**Objective:** Generate the 1 AM aggregate digest.

**Files:**
- Create: `control-panel/scripts/control_center_digest.py`
- Create directory at runtime: `wiki/syntheses/control-center-digests/` or `control-panel/var/digests/` — decide during implementation based on wiki rules.

**Steps:**
1. Load action radar summary.
2. Summarize Claude Code sessions from the past day.
3. Query Gmail/Calendar/Slack if available; mark unavailable otherwise.
4. Write a markdown digest archive.
5. Print Slack-ready digest to stdout.

**Guardrail:** Archive can contain summaries/evidence paths, not raw email bodies or raw private Slack dumps.

## Task 6: Wire Hermes cron at 1 AM

**Objective:** Replace morning-brief behavior with a nightly Control Center digest after validation.

**Cron target:** `#cortana` / origin channel.

**Schedule:** `0 1 * * *`

**Prompt:** Run `control-panel/scripts/control_center_digest.py`, format the output for Slack, explicitly list unavailable sources, and do not recursively schedule jobs.

**Note:** Keep existing morning brief until this job works reliably.

## Task 7: Add biweekly brain lint job

**Objective:** Maintain brain quality without daily noise.

**Schedule:** Every 14 days, early morning after the nightly digest.

**Output:** `#cortana` report with:
- stale pages
- contradictions
- missing source/raw links
- orphaned pages
- suggested ingests

**Guardrail:** Do not auto-fix or auto-ingest; propose fixes for Ricky approval unless the lint rule explicitly allows the edit.

## Task 8: Promote to durable Hermes skill

**Objective:** Make this reusable and self-improving.

**Files:**
- Create Hermes skill: `turnkey-control-center`

**Skill contents:**
- Triggers
- Source list
- digest format
- protected writes
- nightly cron behavior
- brain lint cadence
- Claude Code handoff rules

## Open implementation questions

1. Which Slack channels are allowed as read sources, if any beyond the current thread context?
2. Should nightly digest archive live in `control-panel/var/digests/` or the Obsidian wiki as a `syntheses/`/log artifact?
3. What Gmail labels should define "needs reply" vs FYI?
4. Should the 1 AM digest post immediately, or only post if there are open items?
