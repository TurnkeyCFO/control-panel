"""Agent Manager collector — maps Turnkey Task Scheduler jobs to rich agent metadata
and merges with live stats from master.db and signals.db where available."""
from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from typing import Any

from app import config
from app.collectors import task_scheduler

# ─── Agent registry ─────────────────────────────────────────────────────────
# Maps a task-name prefix (or exact name) → static metadata.
# 'group' groups cards in the UI.  'goal' is the one-line mission statement.
_REGISTRY: list[dict] = [
    # ── Lead-Gen System ──────────────────────────────────────────────────
    {
        "match": "TurnkeyLeadGenListener",
        "label": "Lead Gen · Listener",
        "group": "Lead Gen",
        "goal": "Single-writer daemon: drains events/inbox into master.db in real-time",
        "icon": "📥",
    },
    {
        "match": "TurnkeyLeadGenWatchdog",
        "label": "Lead Gen · Watchdog",
        "group": "Lead Gen",
        "goal": "Restarts Listener if heartbeat goes stale; alerts #assistantbot on repeat failures",
        "icon": "🔒",
    },
    {
        "match": "TurnkeyLeadGenPusher",
        "label": "Lead Gen · Pusher",
        "group": "Lead Gen",
        "goal": "Pushes verified leads to Instantly for outreach; enforces role-filter & catch-all gates",
        "icon": "📤",
    },
    {
        "match": "TurnkeyLeadGenVerifier",
        "label": "Lead Gen · Verifier",
        "group": "Lead Gen",
        "goal": "Runs Reoon verification on pending_verify leads",
        "icon": "✅",
    },
    {
        "match": "TurnkeyLeadGenBackup",
        "label": "Lead Gen · Backup",
        "group": "Lead Gen",
        "goal": "Nightly VACUUM INTO + CSV export → Google Drive (30-day retention)",
        "icon": "💾",
    },
    {
        "match": "TurnkeyLeadGenDailyHealthPing",
        "label": "Lead Gen · Health Ping",
        "group": "Lead Gen",
        "goal": "Daily pipeline health digest to #assistantbot with pipeline metrics",
        "icon": "📊",
    },
    {
        "match": "TurnkeyLeadGenWebhookPull",
        "label": "Lead Gen · Webhook Pull",
        "group": "Lead Gen",
        "goal": "Pulls Instantly webhook events (bounces, replies, unsubscribes) into master.db",
        "icon": "🔗",
    },
    {
        "match": "TurnkeyLeadGenHourly",
        "label": "Lead Gen · Hourly Orchestrator",
        "group": "Lead Gen",
        "goal": "Triggers per-source scrapers each hour within fair-share budget",
        "icon": "⏱",
    },
    {
        "match": "TurnkeyLeadGenStreamProject",
        "label": "Lead Gen · Stream Project",
        "group": "Lead Gen",
        "goal": "Projects master.db → MASTER_LEADS_v1 Google Sheet (nightly rebuild)",
        "icon": "📋",
    },
    {
        "match": "TurnkeyLeadGenSAMGov",
        "label": "Lead Gen · SAM.gov Scraper",
        "group": "Lead Gen",
        "goal": "Scrapes SAM.gov federal contractors as bookkeeping prospects",
        "icon": "🏛",
    },
    {
        "match": "TurnkeyLeadGenBBB",
        "label": "Lead Gen · BBB Scraper",
        "group": "Lead Gen",
        "goal": "Scrapes Better Business Bureau member businesses",
        "icon": "🏢",
    },
    {
        "match": "TurnkeyLeadGenCACSLB",
        "label": "Lead Gen · CA CSLB Scraper",
        "group": "Lead Gen",
        "goal": "Scrapes California Contractors State License Board directory",
        "icon": "🔨",
    },
    {
        "match": "TurnkeyLeadGenUsDirectory",
        "label": "Lead Gen · US Directory",
        "group": "Lead Gen",
        "goal": "DDG-driven nationwide services-business harvester — 5 workers, 5k/day cap",
        "icon": "🌎",
    },
    {
        "match": "TurnkeyChurchScrape",
        "label": "Lead Gen · Church Scraper",
        "group": "Lead Gen",
        "goal": "Scrapes church directories for bookkeeping prospects",
        "icon": "⛪",
    },
    {
        "match": "TurnkeyTxTdlrScrape",
        "label": "Lead Gen · TX TDLR Scraper",
        "group": "Lead Gen",
        "goal": "Scrapes Texas Department of Licensing & Regulation professional directory",
        "icon": "🤠",
    },
    {
        "match": "TurnkeyBookkeepingIntent",
        "label": "Lead Gen · Bookkeeping Intent",
        "group": "Lead Gen",
        "goal": "Monitors Reddit/Twitter for bookkeeping-intent signals (DM prospects, not email)",
        "icon": "🎯",
    },
    # ── COO Orchestrator ─────────────────────────────────────────────────
    {
        "match": "TurnkeyCOO-Listener",
        "label": "COO · Slack Listener",
        "group": "COO",
        "goal": "Socket Mode listener — receives Slack approval taps, routes to approved/ queue",
        "icon": "👂",
    },
    {
        "match": "TurnkeyCOO-Scan",
        "label": "COO · Signal Scanner",
        "group": "COO",
        "goal": "Hourly: scans inbox, FC status, CRM, lead-gen signals for CEO-relevant items",
        "icon": "🔍",
    },
    {
        "match": "TurnkeyCOO-ResearchFetch",
        "label": "COO · Research Fetch",
        "group": "COO",
        "goal": "Hourly: fetches bookkeeping/SMB news and competitive intelligence",
        "icon": "📰",
    },
    {
        "match": "TurnkeyCOO-Propose",
        "label": "COO · Proposal Engine",
        "group": "COO",
        "goal": "Hourly: synthesizes signals → Slack decision cards for Ricky to tap-approve",
        "icon": "💡",
    },
    {
        "match": "TurnkeyCOO-PriorityReload",
        "label": "COO · Priority Reload",
        "group": "COO",
        "goal": "Daily 6am: rebuilds goals_cache.json from CLAUDE.md + wiki for signal scoring",
        "icon": "🎯",
    },
    {
        "match": "TurnkeyCOO-DeepResearch",
        "label": "COO · Deep Research",
        "group": "COO",
        "goal": "Daily 7am Opus synthesis: market, competitive, ops intelligence → wiki",
        "icon": "🧠",
    },
    {
        "match": "TurnkeyCOO-BuildBatch",
        "label": "COO · Build Batch",
        "group": "COO",
        "goal": "Daily 3pm: executes Ricky-approved tasks via tiered Haiku/Sonnet/Opus subagents",
        "icon": "🏗",
    },
    {
        "match": "TurnkeyCOO-WeeklyRollup",
        "label": "COO · Weekly Rollup",
        "group": "COO",
        "goal": "Sunday 4pm: synthesizes week's research + completed tasks into #coo digest",
        "icon": "📅",
    },
    # ── Accounting & Finance ──────────────────────────────────────────────
    {
        "match": "TurnkeyRampClassifier",
        "label": "Ramp Classifier",
        "group": "Accounting",
        "goal": "Daily 7am: fetches uncoded Ramp txns → Opus GL coding → Slack approval gate",
        "icon": "💳",
    },
    {
        "match": "TurnkeyRampApplyFromSheet",
        "label": "Ramp Apply from Sheet",
        "group": "Accounting",
        "goal": "Human-triggered: writes Ricky-approved GL codes back to Ramp via Playwright",
        "icon": "✍",
    },
    {
        "match": "TurnkeyQboClassifier",
        "label": "QBO Classifier",
        "group": "Accounting",
        "goal": "Daily 11am: Playwright scrapes QBO → Opus classifies → Hardik reviews in Sheet",
        "icon": "📚",
    },
    {
        "match": "Turnkey Accountant Daily Push Window",
        "label": "Turnkey Accountant Push",
        "group": "Accounting",
        "goal": "Weekly: pushes Hardik-approved QBO reclassifications to live client books",
        "icon": "⬆",
    },
    # ── CRM & Outreach ────────────────────────────────────────────────────
    {
        "match": "TurnkeyHubspotReport",
        "label": "HubSpot Daily Report",
        "group": "CRM & Outreach",
        "goal": "Daily 5pm: cold-dial analytics digest to #Hubspot-Report",
        "icon": "📣",
    },
    {
        "match": "TurnkeyHubspotListener",
        "label": "HubSpot Listener",
        "group": "CRM & Outreach",
        "goal": "On-startup Socket Mode: answers CRM questions in #Hubspot-Report",
        "icon": "💬",
    },
    # ── Observability & Sync ──────────────────────────────────────────────
    {
        "match": "TurnkeyFinancialCentsScrape",
        "label": "Financial Cents Scraper",
        "group": "Observability",
        "goal": "Twice-daily: Playwright scrapes FC → Ricky-lensed digest to #cortana",
        "icon": "🔄",
    },
    {
        "match": "TurnkeyGranolaSync",
        "label": "Granola Sync",
        "group": "Observability",
        "goal": "Every 4h: Granola meetings → LLM wiki + action items + CRM events",
        "icon": "🎙",
    },
    {
        "match": "TurnkeyHermesKeepalive",
        "label": "Hermes Keepalive",
        "group": "Observability",
        "goal": "Pings Hermes WSL process to prevent sleep; maintains Slack Socket Mode",
        "icon": "💓",
    },
    {
        "match": "TurnkeyFCOpenTabs",
        "label": "FC Open Tabs",
        "group": "Observability",
        "goal": "Opens key Financial Cents tabs in browser on demand",
        "icon": "🌐",
    },
    # ── Infrastructure ────────────────────────────────────────────────────
    {
        "match": "TurnkeyControlPanel-Watchdog",
        "label": "Control Panel Watchdog",
        "group": "Infrastructure",
        "goal": "Restarts control panel server if health check fails",
        "icon": "🛡",
    },
    {
        "match": "TurnkeyControlPanelTunnel",
        "label": "Control Panel Tunnel",
        "group": "Infrastructure",
        "goal": "Cloudflare quick tunnel — token-gated remote access via Slack URL",
        "icon": "🔐",
    },
    {
        "match": "TurnkeyControlPanel",
        "label": "Control Panel Server",
        "group": "Infrastructure",
        "goal": "FastAPI server on :7823 — serves dashboard + all /api/* endpoints",
        "icon": "🖥",
    },
    {
        "match": "TurnkeyDashboardOpen",
        "label": "Dashboard Auto-Open",
        "group": "Infrastructure",
        "goal": "Daily 7am: opens control panel in Chrome so it's front-and-center at day start",
        "icon": "🌅",
    },
    # ── Content Engines ───────────────────────────────────────────────────
    {
        "match": "TurnkeyEtsy",
        "label": "Etsy Trend Scout",
        "group": "Content",
        "goal": "Sunday 6pm: scans Etsy for high-opportunity digital product niches",
        "icon": "🏪",
    },
    {
        "match": "TurnkeyFaithful",
        "label": "Faithful Content Engine",
        "group": "Content",
        "goal": "Weekly: topic discovery → script generation → Slack approval for Faithful brand",
        "icon": "✝",
    },
    {
        "match": "TurnkeyTKCFO",
        "label": "TKCFO Content Engine",
        "group": "Content",
        "goal": "Weekly: topic discovery → script generation → Slack approval for Turnkey CFO brand",
        "icon": "📝",
    },
]

# ─── In-process cache ────────────────────────────────────────────────────────
_CACHE: dict = {"ts": 0.0, "data": None}
_TTL_S = 20.0


def _match_registry(task_name: str) -> dict:
    """Return registry entry for a task name (longest prefix match wins)."""
    best: dict = {}
    best_len = -1
    for entry in _REGISTRY:
        m = entry["match"]
        if task_name.startswith(m) and len(m) > best_len:
            best = entry
            best_len = len(m)
    return best


def _live_stats() -> dict:
    """Pull lightweight live stats from data sources available to the server."""
    out: dict[str, Any] = {}

    # Lead-gen stats
    master_db = (
        config.WORKSPACE_ROOT
        / ".claude" / "Skills" / "lead-gen-master" / "state" / "master.db"
    )
    if master_db.exists():
        try:
            conn = sqlite3.connect(f"file:{master_db}?mode=ro", uri=True, timeout=3)
            conn.row_factory = sqlite3.Row
            with conn:
                row = conn.execute(
                    "SELECT COUNT(*) total, "
                    "SUM(CASE WHEN DATE(scraped_at)=DATE('now') THEN 1 ELSE 0 END) today, "
                    "SUM(CASE WHEN status IN ('pushed','sent','replied','bounced','unsubscribed') THEN 1 ELSE 0 END) pushed, "
                    "SUM(CASE WHEN status='replied' THEN 1 ELSE 0 END) replies "
                    "FROM leads"
                ).fetchone()
                if row:
                    out["lead_gen"] = {
                        "total": row["total"] or 0,
                        "today": row["today"] or 0,
                        "pushed": row["pushed"] or 0,
                        "replies": row["replies"] or 0,
                    }
                hb = conn.execute(
                    "SELECT MAX(heartbeat_at) hb FROM run_log WHERE pipeline='listener'"
                ).fetchone()
                out["lead_gen_listener_hb"] = hb["hb"] if hb else None
        except Exception:
            pass

    # COO signals db
    coo_db = (
        config.WORKSPACE_ROOT
        / "businesses" / "turnkey" / "turnkey-services" / "coo" / "data" / "signals.db"
    )
    if coo_db.exists():
        try:
            conn2 = sqlite3.connect(f"file:{coo_db}?mode=ro", uri=True, timeout=3)
            conn2.row_factory = sqlite3.Row
            with conn2:
                row2 = conn2.execute(
                    "SELECT COUNT(*) pending FROM proposal_history "
                    "WHERE status='pending'"
                ).fetchone()
                out["coo_pending_proposals"] = row2["pending"] if row2 else 0
                row3 = conn2.execute(
                    "SELECT MAX(proposed_at) latest FROM proposal_history"
                ).fetchone()
                out["coo_latest_proposal"] = row3["latest"] if row3 else None
        except Exception:
            pass

    # FC scraper latest.json
    fc_latest = (
        config.WORKSPACE_ROOT
        / "businesses" / "turnkey" / "turnkey-cfo" / "financial-cents-scraper"
        / "data" / "latest.json"
    )
    if fc_latest.exists():
        try:
            import json
            data = json.loads(fc_latest.read_text(encoding="utf-8", errors="replace"))
            out["fc_project_count"] = len(data.get("projects", []))
            out["fc_scraped_at"] = data.get("scraped_at")
        except Exception:
            pass

    return out


def summary() -> dict:
    now = time.time()
    if _CACHE["data"] is not None and (now - _CACHE["ts"]) < _TTL_S:
        return _CACHE["data"]

    # Fetch all Turnkey tasks verbose
    tasks = task_scheduler.list_tasks_verbose(filter_substr="Turnkey")
    live = _live_stats()

    groups: dict[str, list[dict]] = {}
    unmatched: list[dict] = []

    for t in tasks:
        name = t.get("name", "").strip().lstrip("\\")
        entry = _match_registry(name)

        # Determine status badge
        status_raw = (t.get("status") or "").lower()
        state_raw = (t.get("state") or "").lower()
        if "running" in status_raw:
            status = "running"
        elif state_raw == "disabled":
            status = "disabled"
        elif t.get("last_result") == "Success":
            status = "ok"
        elif t.get("last_result") not in ("", "—", "Has not yet run", None):
            status = "warn"
        else:
            status = "idle"

        card: dict = {
            "name": name,
            "label": entry.get("label", name),
            "group": entry.get("group", "Other"),
            "goal": entry.get("goal", ""),
            "icon": entry.get("icon", "⚙"),
            "status": status,
            "state": t.get("state", ""),
            "last_run": t.get("last_run", ""),
            "next_run": t.get("next_run", ""),
            "last_result": t.get("last_result", ""),
            "schedule_label": t.get("schedule_label", ""),
            "repeat_every": t.get("repeat_every", ""),
        }

        # Annotate with live stats for specific agents
        if "Lead Gen" in card["group"] and "lead_gen" in live:
            lg = live["lead_gen"]
            if "Listener" in card["label"]:
                card["live_note"] = f"Heartbeat: {live.get('lead_gen_listener_hb', '—') or '—'}"
            elif "Pusher" in card["label"]:
                card["live_note"] = f"{lg['pushed']:,} pushed · {lg['replies']:,} replies"
            elif "Hourly" in card["label"] or "Scraper" in card["label"] or "Directory" in card["label"]:
                card["live_note"] = f"Today: +{lg['today']:,} · Total: {lg['total']:,}"
        elif card["group"] == "COO":
            if "coo_pending_proposals" in live:
                card["live_note"] = f"{live['coo_pending_proposals']} pending proposals"
        elif "Financial Cents" in card["label"] and "fc_project_count" in live:
            card["live_note"] = f"{live['fc_project_count']} projects scraped · {live.get('fc_scraped_at','')[:16] if live.get('fc_scraped_at') else '—'}"

        grp = card["group"]
        if grp not in groups:
            groups[grp] = []
        if entry:
            groups[grp].append(card)
        else:
            unmatched.append(card)

    # Sort within each group: running first, then by name
    def _sort_key(c: dict) -> tuple:
        order = {"running": 0, "ok": 1, "warn": 2, "idle": 3, "disabled": 4}
        return (order.get(c["status"], 9), c["label"])

    for grp in groups:
        groups[grp].sort(key=_sort_key)
    if unmatched:
        groups["Other"] = sorted(unmatched, key=_sort_key)

    # Compute summary counts
    all_cards = [c for g in groups.values() for c in g]
    counts = {"running": 0, "ok": 0, "warn": 0, "idle": 0, "disabled": 0}
    for c in all_cards:
        counts[c["status"]] = counts.get(c["status"], 0) + 1

    result = {
        "groups": groups,
        "group_order": _GROUP_ORDER,
        "counts": counts,
        "total": len(all_cards),
        "live": live,
    }
    _CACHE["ts"] = now
    _CACHE["data"] = result
    return result


_GROUP_ORDER = [
    "Lead Gen",
    "COO",
    "Accounting",
    "CRM & Outreach",
    "Observability",
    "Content",
    "Infrastructure",
    "Other",
]
