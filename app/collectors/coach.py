"""Read + write adapter for the turnkey-coach coach.db from the control panel."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from app import config

COACH_DB = (
    config.WORKSPACE_ROOT
    / "businesses" / "turnkey" / "turnkey-services" / "internal-ops" / "turnkey-coach" / "coach.db"
)


def _conn() -> sqlite3.Connection:
    COACH_DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(COACH_DB), timeout=10)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.row_factory = sqlite3.Row
    # lazy create so panel never 500s on cold coach.db
    conn.execute(
        """CREATE TABLE IF NOT EXISTS journal_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            source TEXT NOT NULL,
            text TEXT NOT NULL,
            slack_ts TEXT,
            created_at TEXT NOT NULL,
            UNIQUE(source, slack_ts)
        )"""
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_journal_date ON journal_entries(date DESC)")
    conn.execute(
        """CREATE TABLE IF NOT EXISTS weekly_reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            week_start TEXT NOT NULL,
            week_end TEXT NOT NULL,
            narrative TEXT NOT NULL,
            model TEXT,
            created_at TEXT NOT NULL,
            UNIQUE(week_start)
        )"""
    )
    return conn


def list_journal(limit: int = 100) -> list[dict]:
    with _conn() as c:
        rows = c.execute(
            "SELECT id, date, source, text, slack_ts, created_at "
            "FROM journal_entries ORDER BY date DESC, id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


def insert_dashboard_entry(text: str) -> int:
    text = (text or "").strip()
    if not text:
        raise ValueError("empty_text")
    today = datetime.now().date().isoformat()
    now = datetime.now(timezone.utc).isoformat()
    with _conn() as c:
        cur = c.execute(
            "INSERT INTO journal_entries(date, source, text, slack_ts, created_at) VALUES (?,?,?,?,?)",
            (today, "dashboard", text, None, now),
        )
        c.commit()
        return cur.lastrowid


def list_reviews(limit: int = 20) -> list[dict]:
    with _conn() as c:
        rows = c.execute(
            "SELECT week_start, week_end, narrative, model, created_at "
            "FROM weekly_reviews ORDER BY week_start DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


def summary() -> dict:
    with _conn() as c:
        j_count = c.execute("SELECT COUNT(*) FROM journal_entries").fetchone()[0]
        r_count = c.execute("SELECT COUNT(*) FROM weekly_reviews").fetchone()[0]
        latest_j = c.execute(
            "SELECT date, source FROM journal_entries ORDER BY id DESC LIMIT 1"
        ).fetchone()
        latest_r = c.execute(
            "SELECT week_start, week_end FROM weekly_reviews ORDER BY week_start DESC LIMIT 1"
        ).fetchone()
    return {
        "journal_count": j_count,
        "review_count": r_count,
        "latest_journal": dict(latest_j) if latest_j else None,
        "latest_review": dict(latest_r) if latest_r else None,
        "db_path": str(COACH_DB),
        "db_exists": COACH_DB.exists(),
    }
