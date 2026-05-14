import inspect
import json
import time
from pathlib import Path

from app import config

ALLOWED_MODULE_PREFIXES = ("app.collectors.", "app.controls.")
_env_cache: dict | None = None


def _load_env() -> dict:
    global _env_cache
    if _env_cache is None:
        _env_cache = config.env()
    return _env_cache


def _caller_module() -> str:
    frame = inspect.stack()[2].frame
    mod = inspect.getmodule(frame)
    return mod.__name__ if mod else "<unknown>"


def _log_reject(name: str, caller: str) -> None:
    try:
        with open(config.ACTIONS_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "ts": time.time(),
                "event": "secret_access_rejected",
                "name": name,
                "caller": caller,
            }) + "\n")
    except OSError:
        pass


def get(name: str) -> str:
    caller = _caller_module()
    if not any(caller.startswith(p) for p in ALLOWED_MODULE_PREFIXES):
        _log_reject(name, caller)
        return "****"
    return _load_env().get(name, "")


def present(name: str) -> bool:
    return bool(_load_env().get(name))


def last4(name: str) -> str | None:
    v = _load_env().get(name)
    if not v or len(v) < 4:
        return None
    return v[-4:]
