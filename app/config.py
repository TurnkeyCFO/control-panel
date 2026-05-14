import os
from pathlib import Path
from dotenv import dotenv_values

HOST = "127.0.0.1"
PORT = 7823
BASE_URL = f"http://{HOST}:{PORT}"
ALLOWED_HOSTS = {f"{HOST}:{PORT}", f"localhost:{PORT}"}
ALLOWED_ORIGINS = {f"http://{HOST}:{PORT}", f"http://localhost:{PORT}"}

# Set CONTROL_PANEL_TUNNEL_HOST to the tunnel hostname (e.g. from cloudflared)
# so the middleware accepts remote requests from that host.
_TUNNEL_HOST = os.environ.get("CONTROL_PANEL_TUNNEL_HOST", "")
if _TUNNEL_HOST:
    ALLOWED_HOSTS.add(_TUNNEL_HOST)
    ALLOWED_ORIGINS.add(f"https://{_TUNNEL_HOST}")

# Set CONTROL_PANEL_ACCESS_TOKEN for simple bearer-token auth on remote requests.
ACCESS_TOKEN: str = os.environ.get("CONTROL_PANEL_ACCESS_TOKEN", "")

WORKSPACE_ROOT = Path(r"C:\Users\ricky_j3cdbqw\CLAUDE CODE PROJECTS")
ENV_FILE = WORKSPACE_ROOT / ".env"

LOCALAPPDATA = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
DATA_DIR = LOCALAPPDATA / "turnkey-cp"
DATA_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = DATA_DIR / "control-panel.db"
CSRF_FILE = DATA_DIR / "csrf"
ACTIONS_LOG = DATA_DIR / "actions.log"
KILL_SWITCH = DATA_DIR / "kill-switch"

LEARNINGS_DIR = WORKSPACE_ROOT / ".learnings"

# Claude Max plan flat monthly cost. Used to reframe Claude Code "spend" as
# a share of the fixed subscription rather than API-equivalent list prices.
# Override via env CLAUDE_CODE_PLAN_USD if the plan tier changes.
MAX_PLAN_MONTHLY_USD = float(os.environ.get("CLAUDE_CODE_PLAN_USD", "200"))

POLL_INTERVALS = {
    "openrouter": 300,
    "anthropic": 3600,
    "openai": 3600,
    "skills_state": 60,
    "processes": 15,
    "env_audit": 3600,
}


def env() -> dict:
    if not ENV_FILE.exists():
        return {}
    return {k: v for k, v in dotenv_values(ENV_FILE).items() if v is not None}
