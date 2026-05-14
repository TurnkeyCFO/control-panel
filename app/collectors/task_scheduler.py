import csv
import io
import re
import subprocess
import time
from datetime import datetime, timedelta

# In-process cache for the expensive `schtasks /query /v` call.
_VERBOSE_CACHE: dict = {"ts": 0.0, "rows": []}
_VERBOSE_TTL_S = 30.0


# Windows schtasks HRESULTs / exit codes we want to translate for humans.
_LAST_RESULT_MAP = {
    "0": "Success",
    "0x0": "Success",
    "1": "Incorrect function",
    "267009": "Task still running",
    "267011": "Has not yet run",
    "267014": "User terminated",
    "-2147020576": "Operator/user stopped task",
    "-2147024894": "File not found (command path invalid)",
    "-2147216609": "Missing/disabled trigger",
    "-196608": "Last run failed (see task history)",
}


def _decode_last_result(raw: str) -> str:
    v = (raw or "").strip()
    if not v:
        return "—"
    return _LAST_RESULT_MAP.get(v, v)


def list_tasks(filter_substr: str = "") -> list[dict]:
    """Lightweight list for the existing Jobs tab — kept for back-compat."""
    try:
        proc = subprocess.run(
            ["schtasks", "/query", "/fo", "csv", "/nh"],
            capture_output=True, text=True, timeout=15, shell=False,
        )
    except Exception:
        return []
    if proc.returncode != 0:
        return []
    reader = csv.reader(io.StringIO(proc.stdout))
    out = []
    for row in reader:
        if len(row) < 3:
            continue
        name, next_run, status = row[0], row[1], row[2]
        if filter_substr and filter_substr.lower() not in name.lower():
            continue
        out.append({"name": name, "next_run": next_run, "status": status, "source": "task-scheduler"})
    return out


def _fetch_verbose_raw() -> list[dict]:
    """schtasks /v call, cached in-process for _VERBOSE_TTL_S seconds."""
    now = time.time()
    if _VERBOSE_CACHE["rows"] and (now - _VERBOSE_CACHE["ts"]) < _VERBOSE_TTL_S:
        return _VERBOSE_CACHE["rows"]
    try:
        proc = subprocess.run(
            ["schtasks", "/query", "/fo", "csv", "/v"],
            capture_output=True, text=True, timeout=30, shell=False,
        )
    except Exception:
        return _VERBOSE_CACHE["rows"] or []
    if proc.returncode != 0 or not proc.stdout:
        return _VERBOSE_CACHE["rows"] or []

    reader = csv.reader(io.StringIO(proc.stdout))
    header: list[str] | None = None
    rows: list[dict] = []
    for row in reader:
        if not row:
            continue
        if row[0] == "HostName":
            header = [h.strip() for h in row]
            continue
        if header is None or len(row) != len(header):
            continue
        rec = dict(zip(header, row))
        name = rec.get("TaskName", "").strip()
        if name in ("", "TaskName") or name.endswith("TaskName"):
            continue
        rows.append({
            "name": name,
            "status": rec.get("Status", "").strip(),
            "next_run": rec.get("Next Run Time", "").strip(),
            "last_run": rec.get("Last Run Time", "").strip(),
            "last_result_raw": rec.get("Last Result", "").strip(),
            "last_result": _decode_last_result(rec.get("Last Result", "")),
            "schedule_type": rec.get("Schedule Type", "").strip(),
            "start_time": rec.get("Start Time", "").strip(),
            "repeat_every": rec.get("Repeat: Every", "").strip(),
            "task_to_run": rec.get("Task To Run", "").strip(),
            "comment": rec.get("Comment", "").strip(),
            "author": rec.get("Author", "").strip(),
            "state": rec.get("Scheduled Task State", "").strip(),
            "run_as": rec.get("Run As User", "").strip(),
            "logon_mode": rec.get("Logon Mode", "").strip(),
        })
    _VERBOSE_CACHE["ts"] = now
    _VERBOSE_CACHE["rows"] = rows
    return rows


def list_tasks_verbose(filter_substr: str = "") -> list[dict]:
    """Rich listing: name, status, next/last run, last result, schedule, command."""
    all_rows = _fetch_verbose_raw()
    rows = [r for r in all_rows if not filter_substr or filter_substr.lower() in r["name"].lower()]
    rows.sort(key=lambda r: (r["next_run"] in ("", "N/A"), r["next_run"], r["name"]))
    return rows


# ─── Timeline expansion ────────────────────────────────────────────────
_DT_FORMATS = (
    "%m/%d/%Y %I:%M:%S %p",
    "%m/%d/%Y %H:%M:%S",
    "%m/%d/%Y %I:%M %p",
    "%m/%d/%Y %H:%M",
)


def _parse_dt(s: str):
    s = (s or "").strip()
    if not s or s.upper() in ("N/A", "NEVER"):
        return None
    for fmt in _DT_FORMATS:
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            pass
    return None


def _parse_repeat_minutes(s: str) -> int:
    """e.g. '0 Hour(s), 15 Minute(s)' → 15; '1 Hour(s), 0 Minute(s)' → 60."""
    if not s:
        return 0
    hours = 0
    minutes = 0
    m = re.search(r"(\d+)\s*Hour", s, re.I)
    if m:
        hours = int(m.group(1))
    m = re.search(r"(\d+)\s*Minute", s, re.I)
    if m:
        minutes = int(m.group(1))
    return hours * 60 + minutes


_DENSE_STEP_MIN = 30  # repeat ≤ 30min → collapse into a daily "block"


def _expand_schtask(row: dict, window_start: datetime, window_end: datetime) -> dict:
    """Return {'occurrences': [...], 'blocks': [...]} for a single schtasks task."""
    empty = {"occurrences": [], "blocks": []}
    state = (row.get("state") or "").lower()
    if state == "disabled":
        return empty
    next_run = _parse_dt(row.get("next_run", ""))
    sched = (row.get("schedule_type") or "").strip()
    start_time = (row.get("start_time") or "").strip()
    repeat_min = _parse_repeat_minutes(row.get("repeat_every", ""))

    if not next_run and not start_time:
        return empty

    anchor = next_run
    if anchor is None:
        try:
            t = datetime.strptime(start_time, "%I:%M:%S %p").time()
        except ValueError:
            try:
                t = datetime.strptime(start_time, "%H:%M:%S").time()
            except ValueError:
                return empty
        anchor = datetime.combine(window_start.date(), t)

    occurrences: list[datetime] = []
    blocks: list[dict] = []

    if repeat_min and repeat_min > 0:
        if repeat_min <= _DENSE_STEP_MIN:
            # Dense: collapse into one "block" per calendar day inside the window.
            # Assume active all day (most Turnkey dense tasks run 24h).
            day = window_start.date()
            end_day = window_end.date()
            while day <= end_day:
                day_start = datetime.combine(day, datetime.min.time())
                day_end = day_start + timedelta(days=1) - timedelta(seconds=1)
                block_start = max(day_start, window_start)
                block_end = min(day_end, window_end)
                if block_end > block_start:
                    # count occurrences in the day slice
                    count = max(1, int((block_end - block_start).total_seconds() // (repeat_min * 60)))
                    blocks.append({
                        "start_iso": block_start.replace(microsecond=0).isoformat(),
                        "end_iso": block_end.replace(microsecond=0).isoformat(),
                        "step_min": repeat_min,
                        "count": count,
                    })
                day += timedelta(days=1)
        else:
            cursor = anchor
            back = anchor
            while back - timedelta(minutes=repeat_min) >= window_start:
                back -= timedelta(minutes=repeat_min)
                occurrences.append(back)
            while cursor <= window_end:
                occurrences.append(cursor)
                cursor += timedelta(minutes=repeat_min)
    else:
        cadence_days = {"daily": 1, "weekly": 7}.get(sched.lower())
        if cadence_days is None:
            if window_start <= anchor <= window_end:
                occurrences.append(anchor)
        else:
            cur = anchor
            # backfill
            back = anchor
            while back - timedelta(days=cadence_days) >= window_start:
                back -= timedelta(days=cadence_days)
                occurrences.append(back)
            while cur <= window_end:
                if cur >= window_start:
                    occurrences.append(cur)
                cur += timedelta(days=cadence_days)

    base = {
        "name": row["name"],
        "source": "task-scheduler",
        "status": row.get("status", ""),
        "command": row.get("task_to_run", ""),
        "schedule_label": sched or "—",
    }
    return {
        "occurrences": [
            {**base, "start_iso": dt.replace(microsecond=0).isoformat(), "duration_min": 2}
            for dt in occurrences
        ],
        "blocks": [{**base, **b} for b in blocks],
    }


# ─── Minimal cron expander (5-field) ───────────────────────────────────
def _cron_field(expr: str, lo: int, hi: int) -> set[int]:
    """Expand a single cron field to a set of ints."""
    out: set[int] = set()
    for part in expr.split(","):
        p = part.strip()
        step = 1
        if "/" in p:
            p, s = p.split("/", 1)
            step = int(s)
        if p == "*":
            rng = range(lo, hi + 1)
        elif "-" in p:
            a, b = p.split("-", 1)
            rng = range(int(a), int(b) + 1)
        else:
            rng = [int(p)]
        for i in rng:
            if i < lo or i > hi:
                continue
            if (i - lo) % step == 0:
                out.add(i)
    return out


def _expand_cron(expr: str, window_start: datetime, window_end: datetime) -> list[datetime]:
    """5-field cron: minute, hour, dom, month, dow (0-6, 0=Sun)."""
    try:
        parts = expr.split()
        if len(parts) != 5:
            return []
        minutes = _cron_field(parts[0], 0, 59)
        hours = _cron_field(parts[1], 0, 23)
        doms = _cron_field(parts[2], 1, 31)
        months = _cron_field(parts[3], 1, 12)
        dows = _cron_field(parts[4], 0, 6)
    except Exception:
        return []

    hits: list[datetime] = []
    # walk minute-by-minute — window is ≤ 14,400 mins for 10 days, trivial.
    cur = window_start.replace(second=0, microsecond=0)
    while cur <= window_end:
        # cron DOW: 0 = Sun; python weekday(): 0 = Mon → Sunday=6, so map.
        py_dow = cur.weekday()  # 0=Mon
        cron_dow = (py_dow + 1) % 7  # 0=Sun
        if (
            cur.minute in minutes and cur.hour in hours
            and cur.day in doms and cur.month in months
            and cron_dow in dows
        ):
            hits.append(cur)
        cur += timedelta(minutes=1)
    return hits


def list_timeline(days: int = 7) -> dict:
    """Return all job occurrences in the next `days` days plus a short backfill window."""
    now = datetime.now().replace(microsecond=0)
    window_start = now - timedelta(hours=2)  # small backfill so recent runs stay visible
    window_end = now + timedelta(days=max(1, int(days)))

    rows_verbose = list_tasks_verbose(filter_substr="Turnkey")
    occurrences: list[dict] = []
    blocks: list[dict] = []
    seen_jobs: dict[str, dict] = {}
    for r in rows_verbose:
        seen_jobs[r["name"]] = {
            "name": r["name"],
            "source": "task-scheduler",
            "state": r.get("state", ""),
            "status": r.get("status", ""),
            "command": r.get("task_to_run", ""),
            "next_run": r.get("next_run", ""),
            "last_run": r.get("last_run", ""),
            "last_result": r.get("last_result", ""),
            "last_result_raw": r.get("last_result_raw", ""),
            "schedule_label": r.get("schedule_type", ""),
            "repeat_every": r.get("repeat_every", ""),
        }
        exp = _expand_schtask(r, window_start, window_end)
        occurrences.extend(exp["occurrences"])
        blocks.extend(exp["blocks"])

    occurrences.sort(key=lambda o: o["start_iso"])
    blocks.sort(key=lambda b: b["start_iso"])
    return {
        "window_start": window_start.replace(microsecond=0).isoformat(),
        "window_end": window_end.replace(microsecond=0).isoformat(),
        "now": now.isoformat(),
        "jobs": list(seen_jobs.values()),
        "occurrences": occurrences,
        "blocks": blocks,
    }
