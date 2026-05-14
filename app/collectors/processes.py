import psutil


TARGET_NAMES = {"python.exe", "pythonw.exe", "node.exe"}


def list_processes() -> list[dict]:
    out = []
    for p in psutil.process_iter(["pid", "name", "cmdline", "create_time"]):
        try:
            info = p.info
            name = (info.get("name") or "").lower()
            if name not in TARGET_NAMES:
                continue
            cmd = " ".join(info.get("cmdline") or [])
            if not cmd:
                continue
            skill_tag = _tag_from_cmd(cmd)
            if not skill_tag:
                continue
            out.append({
                "pid": info["pid"],
                "name": name,
                "cmd": cmd[:200],
                "skill": skill_tag,
                "started": info.get("create_time"),
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return out


def _tag_from_cmd(cmd: str) -> str | None:
    c = cmd.lower()
    if "claude-maintenance" in c:
        return "claude-maintenance"
    if "tkcfo-content-engine" in c:
        return "tkcfo-content-engine"
    if "faithful-content-engine" in c:
        return "faithful-content-engine"
    if "bill_pay_cron" in c or "bill-pay-automation" in c:
        return "bill-pay"
    if "telegram-agent" in c:
        return "telegram-agent"
    if "industry-site-builder" in c:
        return "industry-site-builder"
    if "research-brief" in c:
        return "research-brief"
    if "control-panel" in c or "uvicorn" in c and "7823" in c:
        return "control-panel"
    return None
