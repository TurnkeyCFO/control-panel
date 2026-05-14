"""
Start a Cloudflare quick tunnel and post the access URL to Slack.
Designed to be run on startup via Task Scheduler.
Launches cloudflared as a truly detached OS process, waits for URL, posts to Slack.
"""
import os
import re
import subprocess
import sys
import time
import threading
from pathlib import Path

CLOUDFLARED = Path(os.environ.get("LOCALAPPDATA", "")) / "turnkey-cp" / "cloudflared.exe"
LOG_DIR = Path(os.environ.get("LOCALAPPDATA", "")) / "turnkey-cp"
TUNNEL_LOG = LOG_DIR / "tunnel.log"
TUNNEL_URL_FILE = LOG_DIR / "tunnel.url"
LOCK_FILE = LOG_DIR / "tunnel.pid"

ENV_FILE = Path(r"C:\Users\ricky_j3cdbqw\CLAUDE CODE PROJECTS\.env")


def _load_env() -> dict:
    result = {}
    if not ENV_FILE.exists():
        return result
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        result[k.strip()] = v.strip().strip('"').strip("'")
    return result


def _kill_existing() -> None:
    if LOCK_FILE.exists():
        try:
            pid = int(LOCK_FILE.read_text().strip())
            subprocess.run(["taskkill", "/F", "/PID", str(pid)], capture_output=True)
        except Exception:
            pass
        try:
            LOCK_FILE.unlink()
        except Exception:
            pass
    subprocess.run(["taskkill", "/F", "/IM", "cloudflared.exe"], capture_output=True)
    time.sleep(1)


def _post_slack(token: str, channel: str, text: str) -> None:
    import urllib.request
    import json as _json
    payload = _json.dumps({"channel": channel, "text": text}).encode()
    req = urllib.request.Request(
        "https://slack.com/api/chat.postMessage",
        data=payload,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    urllib.request.urlopen(req, timeout=10)


def main() -> None:
    env = _load_env()
    slack_token = env.get("SLACK_BOT_TOKEN", "")
    slack_channel = env.get("SLACK_CHANNEL_ASSISTANTBOT", "C0AQVEW4KK8")
    access_token = env.get("CONTROL_PANEL_ACCESS_TOKEN", "")

    LOG_DIR.mkdir(parents=True, exist_ok=True)

    _kill_existing()

    if not CLOUDFLARED.exists():
        msg = f":x: Control Panel tunnel: cloudflared.exe not found at {CLOUDFLARED}"
        if slack_token:
            try:
                _post_slack(slack_token, slack_channel, msg)
            except Exception:
                pass
        sys.exit(1)

    # Open log file for appending stderr
    log_f = open(TUNNEL_LOG, "a", encoding="utf-8", errors="replace")

    proc = subprocess.Popen(
        [str(CLOUDFLARED), "tunnel", "--url", "http://localhost:7823", "--no-autoupdate"],
        stderr=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        text=True,
        encoding="utf-8",
        errors="replace",
        # No creationflags — Task Scheduler already handles detachment
    )

    LOCK_FILE.write_text(str(proc.pid))

    # Scan stderr for the URL (appears within ~10s)
    url = None
    deadline = time.time() + 40
    while time.time() < deadline:
        if proc.poll() is not None:
            log_f.write("cloudflared exited prematurely\n")
            log_f.close()
            if slack_token:
                try:
                    _post_slack(slack_token, slack_channel, ":x: Control Panel tunnel: cloudflared exited before producing a URL")
                except Exception:
                    pass
            sys.exit(1)
        line = proc.stderr.readline()
        if line:
            log_f.write(line)
            log_f.flush()
            m = re.search(r"https://[a-z0-9\-]+\.trycloudflare\.com", line)
            if m:
                url = m.group(0)
                break

    if not url:
        proc.kill()
        log_f.write("Timed out waiting for tunnel URL\n")
        log_f.close()
        if slack_token:
            try:
                _post_slack(slack_token, slack_channel, ":x: Control Panel tunnel: timed out waiting for URL")
            except Exception:
                pass
        sys.exit(1)

    # Save URL for inspection
    TUNNEL_URL_FILE.write_text(url)

    # Drain remaining stderr to log in background thread
    def _drain():
        for ln in proc.stderr:
            log_f.write(ln)
            log_f.flush()
        log_f.close()

    drain_thread = threading.Thread(target=_drain, daemon=True)
    drain_thread.start()

    # Post to Slack
    full_url = f"{url}/?token={access_token}" if access_token else url
    msg = (
        f":satellite: *Control Panel is live*\n"
        f"<{full_url}|Open on phone>\n"
        f"`{full_url}`"
    )
    if slack_token:
        try:
            _post_slack(slack_token, slack_channel, msg)
        except Exception as e:
            log_f.write(f"Slack post failed: {e}\n")

    log_f.write(f"Tunnel up: {url}\n")
    log_f.flush()

    # Keep this script alive so Task Scheduler knows the task is running
    # (and will restart it if cloudflared dies)
    proc.wait()


if __name__ == "__main__":
    main()
