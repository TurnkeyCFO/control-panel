import sqlite3
import threading
from contextlib import contextmanager

from app import config

_lock = threading.Lock()

SCHEMA = """
CREATE TABLE IF NOT EXISTS llm_calls (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts REAL NOT NULL,
    provider TEXT NOT NULL,
    model TEXT,
    skill_tag TEXT,
    tokens_in INTEGER,
    tokens_out INTEGER,
    usd REAL,
    latency_ms INTEGER,
    status TEXT,
    pid INTEGER
);
CREATE INDEX IF NOT EXISTS idx_llm_calls_ts ON llm_calls(ts DESC);
CREATE INDEX IF NOT EXISTS idx_llm_calls_provider ON llm_calls(provider);

CREATE TABLE IF NOT EXISTS provider_usage_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts REAL NOT NULL,
    provider TEXT NOT NULL,
    metric TEXT NOT NULL,
    value_usd REAL,
    value_raw TEXT
);
CREATE INDEX IF NOT EXISTS idx_usage_ts ON provider_usage_snapshots(ts DESC);

CREATE TABLE IF NOT EXISTS job_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    job_id TEXT NOT NULL,
    started_at REAL,
    finished_at REAL,
    status TEXT,
    notes TEXT
);
CREATE INDEX IF NOT EXISTS idx_job_runs_started ON job_runs(started_at DESC);

CREATE TABLE IF NOT EXISTS claude_code_turns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts REAL NOT NULL,
    session_id TEXT NOT NULL,
    turn_uuid TEXT NOT NULL,
    project_slug TEXT,
    model TEXT,
    input_tokens INTEGER,
    output_tokens INTEGER,
    cache_read_tokens INTEGER,
    cache_write_5m_tokens INTEGER,
    cache_write_1h_tokens INTEGER,
    usd REAL,
    UNIQUE(session_id, turn_uuid)
);
CREATE INDEX IF NOT EXISTS idx_cct_ts ON claude_code_turns(ts DESC);
CREATE INDEX IF NOT EXISTS idx_cct_project ON claude_code_turns(project_slug);
CREATE INDEX IF NOT EXISTS idx_cct_model ON claude_code_turns(model);
CREATE INDEX IF NOT EXISTS idx_cct_session ON claude_code_turns(session_id);

CREATE TABLE IF NOT EXISTS action_audit (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts REAL NOT NULL,
    route TEXT,
    skill_id TEXT,
    origin TEXT,
    csrf_ok INTEGER,
    outcome TEXT
);

CREATE TABLE IF NOT EXISTS action_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts REAL NOT NULL,
    source TEXT NOT NULL,
    source_ref TEXT,
    category TEXT NOT NULL DEFAULT 'general',
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
CREATE INDEX IF NOT EXISTS idx_action_items_category ON action_items(category, status);

CREATE TABLE IF NOT EXISTS executive_notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts REAL NOT NULL,
    note_type TEXT NOT NULL DEFAULT 'note',
    title TEXT,
    body TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT 'control-panel',
    status TEXT NOT NULL DEFAULT 'open'
);
CREATE INDEX IF NOT EXISTS idx_executive_notes_ts ON executive_notes(ts DESC);

CREATE TABLE IF NOT EXISTS control_center_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts REAL NOT NULL,
    run_type TEXT NOT NULL,
    status TEXT NOT NULL,
    summary_path TEXT,
    notes TEXT
);
CREATE INDEX IF NOT EXISTS idx_control_center_runs_ts ON control_center_runs(ts DESC);
"""


def init_db() -> None:
    with _lock:
        conn = sqlite3.connect(config.DB_PATH)
        conn.executescript(SCHEMA)
        conn.commit()
        conn.close()


@contextmanager
def connect():
    with _lock:
        conn = sqlite3.connect(config.DB_PATH)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()


def recent_llm_calls(limit: int = 50):
    with connect() as c:
        rows = c.execute("SELECT * FROM llm_calls ORDER BY ts DESC LIMIT ?", (limit,)).fetchall()
    return [dict(r) for r in rows]


def spend_summary():
    with connect() as c:
        totals = c.execute("""
            SELECT provider, SUM(usd) AS mtd
            FROM llm_calls
            WHERE ts >= strftime('%s', 'now', 'start of month')
            GROUP BY provider
        """).fetchall()
        today = c.execute("""
            SELECT provider, SUM(usd) AS today
            FROM llm_calls
            WHERE ts >= strftime('%s', 'now', 'start of day')
            GROUP BY provider
        """).fetchall()
    today_map = {r["provider"]: r["today"] or 0 for r in today}
    return [
        {"provider": r["provider"], "today": today_map.get(r["provider"], 0), "mtd": r["mtd"] or 0}
        for r in totals
    ]


def recent_jobs(limit: int = 50):
    with connect() as c:
        rows = c.execute(
            "SELECT * FROM job_runs ORDER BY started_at DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]


def timeseries_spend_daily(days: int = 30) -> list[dict]:
    with connect() as c:
        rows = c.execute(f"""
            SELECT
                strftime('%Y-%m-%d', ts, 'unixepoch', 'localtime') AS day,
                provider,
                SUM(COALESCE(usd, 0)) AS usd
            FROM llm_calls
            WHERE ts >= strftime('%s', 'now', '-{int(days)} days')
            GROUP BY day, provider
            ORDER BY day ASC
        """).fetchall()
    return [dict(r) for r in rows]


def timeseries_activity_hourly(hours: int = 24) -> list[dict]:
    with connect() as c:
        rows = c.execute(f"""
            SELECT
                strftime('%Y-%m-%d %H:00', ts, 'unixepoch', 'localtime') AS hour,
                skill_tag,
                COUNT(*) AS calls,
                SUM(COALESCE(tokens_in, 0) + COALESCE(tokens_out, 0)) AS tokens
            FROM llm_calls
            WHERE ts >= strftime('%s', 'now', '-{int(hours)} hours')
            GROUP BY hour, skill_tag
            ORDER BY hour ASC
        """).fetchall()
    return [dict(r) for r in rows]


def breakdown_by_skill(days: int = 30) -> list[dict]:
    with connect() as c:
        rows = c.execute(f"""
            SELECT
                COALESCE(skill_tag, 'untagged') AS skill_tag,
                COUNT(*) AS calls,
                SUM(COALESCE(usd, 0)) AS usd,
                SUM(COALESCE(tokens_in, 0)) AS tokens_in,
                SUM(COALESCE(tokens_out, 0)) AS tokens_out
            FROM llm_calls
            WHERE ts >= strftime('%s', 'now', '-{int(days)} days')
            GROUP BY skill_tag
            ORDER BY usd DESC
        """).fetchall()
    return [dict(r) for r in rows]


def breakdown_by_model(days: int = 30) -> list[dict]:
    with connect() as c:
        rows = c.execute(f"""
            SELECT
                COALESCE(model, 'unknown') AS model,
                COUNT(*) AS calls,
                SUM(COALESCE(usd, 0)) AS usd,
                AVG(COALESCE(latency_ms, 0)) AS avg_latency_ms
            FROM llm_calls
            WHERE ts >= strftime('%s', 'now', '-{int(days)} days')
            GROUP BY model
            ORDER BY usd DESC
        """).fetchall()
    return [dict(r) for r in rows]


def record_action(route: str, skill_id: str, origin: str, csrf_ok: bool, outcome: str) -> None:
    import time
    with connect() as c:
        c.execute(
            "INSERT INTO action_audit (ts, route, skill_id, origin, csrf_ok, outcome) VALUES (?, ?, ?, ?, ?, ?)",
            (time.time(), route, skill_id, origin, 1 if csrf_ok else 0, outcome),
        )


def upsert_action_item(row: dict) -> int:
    import time
    now = float(row.get("ts") or time.time())
    values = {
        "ts": now,
        "source": row.get("source") or "manual",
        "source_ref": row.get("source_ref") or row.get("title") or "",
        "category": row.get("category") or "general",
        "title": row.get("title") or "Untitled action",
        "detail": row.get("detail") or "",
        "priority": row.get("priority") or "normal",
        "owner": row.get("owner") or "ricky",
        "status": row.get("status") or "open",
        "recommended_action": row.get("recommended_action") or "",
        "evidence_path": row.get("evidence_path") or "",
        "expires_at": row.get("expires_at"),
    }
    with connect() as c:
        c.execute("""
            INSERT INTO action_items (
                ts, source, source_ref, category, title, detail, priority, owner, status,
                recommended_action, evidence_path, expires_at
            ) VALUES (:ts, :source, :source_ref, :category, :title, :detail, :priority, :owner, :status,
                :recommended_action, :evidence_path, :expires_at)
            ON CONFLICT(source, source_ref, title) DO UPDATE SET
                ts=excluded.ts,
                category=excluded.category,
                detail=excluded.detail,
                priority=excluded.priority,
                owner=excluded.owner,
                status=excluded.status,
                recommended_action=excluded.recommended_action,
                evidence_path=excluded.evidence_path,
                expires_at=excluded.expires_at
        """, values)
        row_id = c.execute(
            "SELECT id FROM action_items WHERE source=? AND source_ref=? AND title=?",
            (values["source"], values["source_ref"], values["title"]),
        ).fetchone()["id"]
    return int(row_id)


def open_action_items(limit: int = 100) -> list[dict]:
    with connect() as c:
        rows = c.execute("""
            SELECT * FROM action_items
            WHERE status IN ('open', 'pending', 'watch')
            ORDER BY CASE priority WHEN 'critical' THEN 0 WHEN 'high' THEN 1 WHEN 'normal' THEN 2 WHEN 'low' THEN 3 ELSE 4 END,
                     ts DESC
            LIMIT ?
        """, (limit,)).fetchall()
    return [dict(r) for r in rows]


def add_executive_note(body: str, title: str = "", note_type: str = "note", source: str = "control-panel", status: str = "open") -> int:
    import time
    if not body or not body.strip():
        raise ValueError("empty_note")
    with connect() as c:
        cur = c.execute(
            "INSERT INTO executive_notes (ts, note_type, title, body, source, status) VALUES (?, ?, ?, ?, ?, ?)",
            (time.time(), note_type or "note", title or "", body.strip(), source or "control-panel", status or "open"),
        )
        return int(cur.lastrowid)


def list_executive_notes(limit: int = 50) -> list[dict]:
    with connect() as c:
        rows = c.execute("SELECT * FROM executive_notes ORDER BY ts DESC LIMIT ?", (limit,)).fetchall()
    return [dict(r) for r in rows]


def record_control_center_run(run_type: str, status: str, summary_path: str = "", notes: str = "") -> int:
    import time
    with connect() as c:
        cur = c.execute(
            "INSERT INTO control_center_runs (ts, run_type, status, summary_path, notes) VALUES (?, ?, ?, ?, ?)",
            (time.time(), run_type, status, summary_path or "", notes or ""),
        )
        return int(cur.lastrowid)


def recent_control_center_runs(limit: int = 10) -> list[dict]:
    with connect() as c:
        rows = c.execute("SELECT * FROM control_center_runs ORDER BY ts DESC LIMIT ?", (limit,)).fetchall()
    return [dict(r) for r in rows]
