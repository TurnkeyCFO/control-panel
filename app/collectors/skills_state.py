from pathlib import Path

from app import config

WS = config.WORKSPACE_ROOT
SKILLS_DIR = WS / ".claude" / "Skills"


def list_skill_states() -> list[dict]:
    if not SKILLS_DIR.exists():
        return []
    out = []
    for sd in sorted(SKILLS_DIR.iterdir()):
        if not sd.is_dir():
            continue
        state_file = sd / "state" / "active.md"
        purpose_file = sd / "SKILL.md"
        purpose = ""
        if purpose_file.exists():
            try:
                lines = purpose_file.read_text(encoding="utf-8").splitlines()[:20]
                for ln in lines:
                    ln = ln.strip()
                    if ln and not ln.startswith("#") and not ln.startswith("---") and not ln.startswith("name:") and not ln.startswith("description:"):
                        purpose = ln[:120]
                        break
            except Exception:
                pass
        state_preview = ""
        if state_file.exists():
            try:
                state_preview = state_file.read_text(encoding="utf-8")[:300]
            except Exception:
                pass
        out.append({
            "name": sd.name,
            "purpose": purpose,
            "has_state": state_file.exists(),
            "state_preview": state_preview,
        })
    return out


def recent_errors(limit: int = 10) -> list[str]:
    err_file = config.LEARNINGS_DIR / "ERRORS.md"
    if not err_file.exists():
        return []
    try:
        text = err_file.read_text(encoding="utf-8")
    except Exception:
        return []
    blocks = [b.strip() for b in text.split("\n## ") if b.strip()]
    return [("## " + b)[:400] for b in blocks[:limit]]
