"""Read-only adapter for the lead-gen-master master.db."""
from __future__ import annotations

import sqlite3
from pathlib import Path

from app import config

MASTER_DB = (
    config.WORKSPACE_ROOT
    / ".claude" / "Skills" / "lead-gen-master" / "state" / "master.db"
)


def _conn() -> sqlite3.Connection | None:
    if not MASTER_DB.exists():
        return None
    conn = sqlite3.connect(f"file:{MASTER_DB}?mode=ro", uri=True, timeout=5)
    conn.row_factory = sqlite3.Row
    return conn


def _empty_summary() -> dict:
    return {
        "db_exists": MASTER_DB.exists(),
        "db_path": str(MASTER_DB),
        "total_leads": 0,
        "scraped_today": 0,
        "pending_verify": 0,
        "valid": 0,
        "pushed": 0,
        "sent": 0,
        "replies": 0,
        "bounces": 0,
        "suppressed": 0,
        "role_filtered": 0,
        "budget_used_today": 0,
        "budget_cap_today": 0,
        "latest_scrape_at": None,
        "latest_listener_heartbeat": None,
    }


def summary() -> dict:
    conn = _conn()
    if conn is None:
        return _empty_summary()
    out = _empty_summary()
    with conn:
        c = conn
        out["total_leads"] = c.execute("SELECT COUNT(*) FROM leads").fetchone()[0]
        out["scraped_today"] = c.execute(
            "SELECT COUNT(*) FROM leads WHERE DATE(scraped_at) = DATE('now')"
        ).fetchone()[0]
        status_rows = {r["status"]: r["n"] for r in c.execute(
            "SELECT status, COUNT(*) n FROM leads GROUP BY status"
        )}
        out["pending_verify"] = status_rows.get("pending_verify", 0)
        out["role_filtered"] = status_rows.get("role_filtered", 0)
        out["pushed"] = status_rows.get("pushed", 0) + status_rows.get("sent", 0) + status_rows.get("replied", 0) + status_rows.get("bounced", 0) + status_rows.get("unsubscribed", 0)
        out["sent"] = status_rows.get("sent", 0) + status_rows.get("replied", 0) + status_rows.get("bounced", 0) + status_rows.get("unsubscribed", 0)
        out["replies"] = status_rows.get("replied", 0)
        out["bounces"] = status_rows.get("bounced", 0)
        out["valid"] = c.execute(
            "SELECT COUNT(*) FROM leads WHERE verification_status = 'valid'"
        ).fetchone()[0]
        out["suppressed"] = c.execute("SELECT COUNT(*) FROM suppression").fetchone()[0]

        budget = c.execute(
            "SELECT used, cap FROM scrape_budget WHERE source='__total__' AND date=DATE('now')"
        ).fetchone()
        if budget:
            out["budget_used_today"] = budget["used"] or 0
            out["budget_cap_today"] = budget["cap"] or 0

        latest = c.execute(
            "SELECT MAX(scraped_at) FROM leads"
        ).fetchone()[0]
        out["latest_scrape_at"] = latest

        hb = c.execute(
            "SELECT MAX(heartbeat_at) FROM run_log WHERE pipeline='listener'"
        ).fetchone()[0]
        out["latest_listener_heartbeat"] = hb
    return out


def by_source_daily(days: int = 14) -> list[dict]:
    conn = _conn()
    if conn is None:
        return []
    with conn:
        rows = conn.execute(
            "SELECT DATE(scraped_at) day, source, COUNT(*) n "
            "FROM leads "
            "WHERE scraped_at >= DATE('now', ?) "
            "GROUP BY day, source ORDER BY day",
            (f"-{max(1, int(days))} days",),
        ).fetchall()
    return [dict(r) for r in rows]


def status_breakdown() -> list[dict]:
    conn = _conn()
    if conn is None:
        return []
    with conn:
        rows = conn.execute(
            "SELECT COALESCE(status,'unknown') status, COUNT(*) n "
            "FROM leads GROUP BY status ORDER BY n DESC"
        ).fetchall()
    return [dict(r) for r in rows]


def source_breakdown() -> list[dict]:
    conn = _conn()
    if conn is None:
        return []
    with conn:
        rows = conn.execute(
            "SELECT source, COUNT(*) n FROM leads GROUP BY source ORDER BY n DESC"
        ).fetchall()
    return [dict(r) for r in rows]


def recent_runs(limit: int = 25) -> list[dict]:
    conn = _conn()
    if conn is None:
        return []
    with conn:
        rows = conn.execute(
            "SELECT run_id, pipeline, started_at, finished_at, heartbeat_at, "
            "scraped, verified, pushed, errors, notes "
            "FROM run_log ORDER BY started_at DESC LIMIT ?",
            (int(limit),),
        ).fetchall()
    return [dict(r) for r in rows]


def scrape_budget_today() -> list[dict]:
    conn = _conn()
    if conn is None:
        return []
    with conn:
        rows = conn.execute(
            "SELECT source, used, cap, benched_until "
            "FROM scrape_budget WHERE date = DATE('now') ORDER BY used DESC"
        ).fetchall()
    return [dict(r) for r in rows]


def aggregate_by_source(days: int) -> list[dict]:
    """Per-source totals within the last `days` days across every pipeline metric."""
    conn = _conn()
    if conn is None:
        return []
    d = max(1, int(days))
    window = f"-{d} days"
    with conn:
        rows = conn.execute(
            """
            SELECT
              source,
              COUNT(*)                                                    AS scraped,
              SUM(CASE WHEN verification_status='valid'       THEN 1 ELSE 0 END) AS valid,
              SUM(CASE WHEN verification_status='invalid'     THEN 1 ELSE 0 END) AS invalid,
              SUM(CASE WHEN verification_status='catch_all'   THEN 1 ELSE 0 END) AS catch_all,
              SUM(CASE WHEN verification_status='role'        THEN 1 ELSE 0 END) AS role,
              SUM(CASE WHEN verification_status='unknown'     THEN 1 ELSE 0 END) AS unknown,
              SUM(CASE WHEN verification_status IS NULL       THEN 1 ELSE 0 END) AS unverified,
              SUM(CASE WHEN status='pushed'                   THEN 1 ELSE 0 END) AS pushed,
              SUM(CASE WHEN status='sent'                     THEN 1 ELSE 0 END) AS sent,
              SUM(CASE WHEN status='replied'                  THEN 1 ELSE 0 END) AS replied,
              SUM(CASE WHEN status='bounced'                  THEN 1 ELSE 0 END) AS bounced,
              SUM(CASE WHEN status='unsubscribed'             THEN 1 ELSE 0 END) AS unsubscribed,
              SUM(CASE WHEN status='suppressed'               THEN 1 ELSE 0 END) AS suppressed
            FROM leads
            WHERE scraped_at >= DATETIME('now', ?)
            GROUP BY source
            ORDER BY scraped DESC
            """,
            (window,),
        ).fetchall()
    return [dict(r) for r in rows]


def aggregate_timeseries(days: int, metric: str = "scraped") -> list[dict]:
    """Bucketed time series per source, bucket size auto-picked by window size."""
    conn = _conn()
    if conn is None:
        return []
    d = max(1, int(days))
    # bucket format: <=35d → day, <=180d → week, else month
    if d <= 35:
        bucket = "%Y-%m-%d"
    elif d <= 180:
        bucket = "%Y-W%W"
    else:
        bucket = "%Y-%m"

    date_col = "scraped_at"
    where_extra = ""
    if metric == "valid":
        where_extra = "AND verification_status='valid'"
    elif metric == "invalid":
        where_extra = "AND verification_status IN ('invalid','catch_all','role')"
    elif metric == "pushed":
        date_col = "COALESCE(pushed_at, scraped_at)"
        where_extra = "AND status IN ('pushed','sent','replied','bounced','unsubscribed')"
    elif metric == "replied":
        date_col = "COALESCE(reply_at, scraped_at)"
        where_extra = "AND status='replied'"
    elif metric == "bounced":
        date_col = "COALESCE(last_bounce_at, scraped_at)"
        where_extra = "AND status='bounced'"

    window = f"-{d} days"
    sql = f"""
        SELECT strftime('{bucket}', {date_col}) bucket, source, COUNT(*) n
        FROM leads
        WHERE {date_col} >= DATETIME('now', ?)
          {where_extra}
        GROUP BY bucket, source
        ORDER BY bucket
    """
    with conn:
        rows = conn.execute(sql, (window,)).fetchall()
    return [dict(r) for r in rows]


def recent_transitions(limit: int = 20) -> list[dict]:
    conn = _conn()
    if conn is None:
        return []
    with conn:
        rows = conn.execute(
            "SELECT lead_id, from_state, to_state, transition_at, reason "
            "FROM state_log ORDER BY id DESC LIMIT ?",
            (int(limit),),
        ).fetchall()
    return [dict(r) for r in rows]
