from __future__ import annotations

import os
import re
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from app import config
from app.db import (
    add_executive_note,
    list_executive_notes,
    open_action_items,
    recent_control_center_runs,
    recent_jobs,
    recent_llm_calls,
    record_control_center_run,
    upsert_action_item,
)

WIKI_ROOT = Path("/mnt/c/Users/ricky_j3cdbqw/CLAUDE CODE PROJECTS/CLAUDE CODE 2ND BRAIN/wiki")
CLAUDE_PROJECTS = Path.home() / ".claude" / "projects"
SECRET_RE = re.compile(r"(?i)(api[_-]?key|token|secret|password|bearer)\s*[:=]\s*[^\s]+")


def _redact(text: str) -> str:
    return SECRET_RE.sub(lambda m: m.group(0).split(m.group(1))[0] + m.group(1) + "=[REDACTED]", text or "")


def _read_tail(path: Path, chars: int = 5000) -> str:
    try:
        data = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""
    return data[-chars:]


def _wiki_signals() -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    items: list[dict[str, Any]] = []
    unavailable: list[dict[str, str]] = []
    if not WIKI_ROOT.exists():
        return items, [{"source": "Obsidian brain", "status": "unavailable", "detail": f"Wiki path not found: {WIKI_ROOT}"}]

    log_tail = _read_tail(WIKI_ROOT / "log.md", 6000)
    index_tail = _read_tail(WIKI_ROOT / "index.md", 3000)
    if log_tail:
        upsert_action_item({
            "source": "obsidian",
            "source_ref": "wiki/log.md",
            "category": "brain",
            "title": "Second brain has fresh context to review",
            "detail": "Recent wiki log entries are available for the Control Center first pass.",
            "priority": "normal",
            "recommended_action": "Review Brain Maintenance for stale context, open questions, and useful ingests.",
            "evidence_path": str(WIKI_ROOT / "log.md"),
        })
        items.append({
            "source": "obsidian",
            "category": "brain",
            "priority": "normal",
            "title": "Review latest second-brain context",
            "detail": _redact(" ".join(log_tail.splitlines()[-8:]))[:900],
            "recommended_action": "Use this as the context anchor for today's priorities.",
            "evidence_path": str(WIKI_ROOT / "log.md"),
        })
    if index_tail:
        items.append({
            "source": "obsidian",
            "category": "brain",
            "priority": "low",
            "title": "Brain index available",
            "detail": "Index loaded; durable claims should cite source pages before external use.",
            "recommended_action": "Drill into 1–3 pages when a specific decision needs context.",
            "evidence_path": str(WIKI_ROOT / "index.md"),
        })
    return items, unavailable


def _system_signals() -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    jobs = recent_jobs(20)
    failed = [j for j in jobs if str(j.get("status") or "").lower() in {"failed", "error"}]
    if failed:
        items.append({
            "source": "control-panel",
            "category": "ops",
            "priority": "high",
            "title": f"{len(failed)} recent job(s) need review",
            "detail": "; ".join(_redact(f"{j.get('source')}:{j.get('job_id')} {j.get('notes') or ''}") for j in failed[:3]),
            "recommended_action": "Open Scheduled Jobs and inspect the failed run logs.",
            "evidence_path": str(config.DB_PATH),
        })
    calls = recent_llm_calls(20)
    if calls:
        items.append({
            "source": "control-panel",
            "category": "ops",
            "priority": "low",
            "title": "Recent Hermes activity is flowing",
            "detail": f"{len(calls)} recent LLM call records found in telemetry.",
            "recommended_action": "Use analytics tabs only when debugging cost/activity; daily focus belongs in Control Center.",
            "evidence_path": str(config.DB_PATH),
        })
    return items


def _claude_activity() -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    since = time.time() - 36 * 3600
    count = 0
    projects: dict[str, int] = {}
    try:
        from app.collectors import claude_code
        claude_code.scan()
        for row in claude_code.top_sessions(days=2, limit=8):
            count += int(row.get("turns") or 0)
            project = row.get("project_slug") or "unknown"
            projects[project] = projects.get(project, 0) + int(row.get("turns") or 0)
    except Exception:
        pass
    if projects:
        top = sorted(projects.items(), key=lambda kv: kv[1], reverse=True)[:5]
        items.append({
            "source": "claude-code",
            "category": "workstream",
            "priority": "normal",
            "title": "Claude Code workstreams active recently",
            "detail": ", ".join(f"{k}: {v} turns" for k, v in top),
            "recommended_action": "Review Notes & Actions and promote true follow-ups into action items.",
            "evidence_path": str(CLAUDE_PROJECTS),
        })
    elif CLAUDE_PROJECTS.exists():
        items.append({
            "source": "claude-code",
            "category": "workstream",
            "priority": "low",
            "title": "Claude Code logs are available",
            "detail": "No recent summarized sessions surfaced by the usage collector.",
            "recommended_action": "Run a manual Claude Code scan if expected work is missing.",
            "evidence_path": str(CLAUDE_PROJECTS),
        })
    return items


def _availability() -> list[dict[str, str]]:
    env = {**os.environ, **config.env()}
    unavailable: list[dict[str, str]] = []
    if not any(env.get(k) for k in ("SLACK_BOT_TOKEN", "SLACK_USER_TOKEN", "HERMES_SLACK_TOKEN")):
        unavailable.append({"source": "Slack", "status": "unavailable", "detail": "No Slack read token configured for the control-panel app; current thread context only is available to Hermes."})
    if not any(env.get(k) for k in ("GOOGLE_APPLICATION_CREDENTIALS", "GMAIL_TOKEN", "GWS_CREDENTIALS")):
        unavailable.append({"source": "Email", "status": "unavailable", "detail": "No Gmail/Google Workspace read credential detected in control-panel environment."})
    if not any(env.get(k) for k in ("GOOGLE_APPLICATION_CREDENTIALS", "GCAL_TOKEN", "GWS_CREDENTIALS")):
        unavailable.append({"source": "Calendar", "status": "unavailable", "detail": "No Google Calendar read credential detected in control-panel environment."})
    return unavailable


def _group(items: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    groups = {"needs_ricky": [], "morning_brief": [], "today": [], "this_week": [], "action_radar": [], "brain_maintenance": [], "ops_systems": []}
    for item in items:
        cat = item.get("category") or "general"
        pri = item.get("priority") or "normal"
        if pri in {"critical", "high"} or item.get("owner") == "ricky":
            groups["needs_ricky"].append(item)
        if cat in {"calendar", "today"}:
            groups["today"].append(item)
        elif cat in {"week", "workstream"}:
            groups["this_week"].append(item)
        elif cat == "brain":
            groups["brain_maintenance"].append(item)
        elif cat in {"ops", "system"}:
            groups["ops_systems"].append(item)
        groups["action_radar"].append(item)
    groups["morning_brief"] = groups["needs_ricky"][:5] or groups["action_radar"][:5]
    return groups


def summary(refresh: bool = False) -> dict[str, Any]:
    if refresh:
        seed_default_actions()
    db_items = open_action_items(100)
    wiki_items, wiki_unavailable = _wiki_signals()
    items = db_items + wiki_items + _claude_activity() + _system_signals()
    unavailable = wiki_unavailable + _availability()
    notes = list_executive_notes(25)
    generated_at = time.time()
    return {
        "generated_at": generated_at,
        "generated_at_iso": datetime.fromtimestamp(generated_at).isoformat(timespec="seconds"),
        "items": items,
        "groups": _group(items),
        "notes": notes,
        "runs": recent_control_center_runs(10),
        "unavailable": unavailable,
        "brief": build_brief(items, unavailable),
    }


def seed_default_actions() -> None:
    defaults = [
        {
            "source": "ricky-request",
            "source_ref": "2026-05-14-control-center",
            "category": "today",
            "title": "Review first Control Center draft",
            "detail": "Ricky asked for a true day/week command center layered into the existing Control Panel.",
            "priority": "high",
            "recommended_action": "Open the Control Center tab, review Morning Brief and Notes & Actions, then approve the next integration pass.",
            "evidence_path": "Slack #cortana thread 1778776910.022299",
        },
        {
            "source": "ricky-request",
            "source_ref": "dashboard-command-only",
            "category": "workstream",
            "title": "Keep client dashboards command-only",
            "detail": "Client delivery dashboards should not enter the recurring daily loop until Ricky asks at Hawk/when ready.",
            "priority": "normal",
            "recommended_action": "Use dashboard tab only on explicit client-dashboard commands.",
            "evidence_path": "Slack #cortana thread 1778776910.022299",
        },
    ]
    for row in defaults:
        upsert_action_item(row)


def build_brief(items: list[dict[str, Any]], unavailable: list[dict[str, str]]) -> str:
    today = datetime.now().strftime("%A, %B %-d, %Y") if os.name != "nt" else datetime.now().strftime("%A, %B %#d, %Y")
    ranked = items[:5]
    lines = [f"Turnkey Control Center — {today}", "", "Needs Ricky today"]
    if ranked:
        for i, item in enumerate(ranked, 1):
            lines.append(f"{i}. [{item.get('priority','normal')}] {item.get('title','Untitled')}")
            if item.get("recommended_action"):
                lines.append(f"   → {item.get('recommended_action')}")
            if item.get("evidence_path"):
                lines.append(f"   Evidence: {item.get('source')} — {item.get('evidence_path')}")
    else:
        lines.append("- No open items surfaced yet.")
    lines.extend(["", "Unavailable sources"])
    if unavailable:
        for u in unavailable:
            lines.append(f"- {u['source']}: {u['detail']}")
    else:
        lines.append("- None reported.")
    return "\n".join(lines)


def add_note(body: str, title: str = "", note_type: str = "note") -> dict[str, Any]:
    note_id = add_executive_note(body=body, title=title, note_type=note_type, source="control-panel")
    return {"ok": True, "id": note_id}


def record_run(run_type: str, status: str, summary_path: str = "", notes: str = "") -> int:
    return record_control_center_run(run_type, status, summary_path, notes)
