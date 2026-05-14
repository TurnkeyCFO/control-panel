import json
import secrets as _secrets
import subprocess
import sys
import threading
import time

from app import config
from app.controls import registry
from app.db import connect

_pending_nonces: dict[str, tuple[str, float]] = {}
_lock = threading.Lock()


def issue_nonce(skill_id: str) -> str:
    spec = registry.get(skill_id)
    if spec is None:
        raise ValueError("unknown_skill")
    nonce = _secrets.token_urlsafe(16)
    with _lock:
        _pending_nonces[nonce] = (skill_id, time.time())
    return nonce


def _consume_nonce(skill_id: str, nonce: str) -> bool:
    with _lock:
        record = _pending_nonces.pop(nonce, None)
    if record is None:
        return False
    bound_skill, issued_at = record
    if bound_skill != skill_id:
        return False
    if time.time() - issued_at > 30:
        return False
    return True


def run(skill_id: str, *, nonce: str | None = None) -> dict:
    spec = registry.get(skill_id)
    if spec is None:
        return {"ok": False, "error": "unknown_skill"}

    if spec.write_action:
        if not nonce or not _consume_nonce(skill_id, nonce):
            return {"ok": False, "error": "nonce_required_or_expired"}

    started = time.time()
    with connect() as c:
        cur = c.execute(
            "INSERT INTO job_runs (source, job_id, started_at, status) VALUES (?, ?, ?, ?)",
            ("control-panel", skill_id, started, "running"),
        )
        run_id = cur.lastrowid

    try:
        proc = subprocess.run(
            list(spec.argv),
            cwd=str(spec.cwd),
            shell=False,
            capture_output=True,
            text=True,
            timeout=600,
        )
        ok = proc.returncode == 0
        status = "ok" if ok else "failed"
        notes = (proc.stderr or proc.stdout or "")[-500:]
    except Exception as e:
        ok = False
        status = "error"
        notes = f"{type(e).__name__}: {e}"[:500]

    finished = time.time()
    with connect() as c:
        c.execute(
            "UPDATE job_runs SET finished_at=?, status=?, notes=? WHERE id=?",
            (finished, status, notes, run_id),
        )

    try:
        with open(config.ACTIONS_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "ts": finished,
                "event": "skill_run",
                "skill_id": skill_id,
                "status": status,
                "duration_ms": int((finished - started) * 1000),
            }) + "\n")
    except OSError:
        pass

    return {"ok": ok, "status": status, "run_id": run_id}
