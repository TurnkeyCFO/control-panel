#!/usr/bin/env python3
"""Generate a first-draft Turnkey Control Center digest.

This script is local/read-only. It asks the control_center collector for the
current summary, writes a markdown artifact, and prints both the artifact path
and the digest text for Slack/Hermes delivery.
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.collectors import control_center  # noqa: E402


def main() -> int:
    data = control_center.summary(refresh=True)
    brief = data.get("brief") or "Turnkey Control Center\n\nNo brief generated."
    generated = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    out_dir = ROOT / "artifacts" / "control-center"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{generated}-digest.md"

    unavailable = data.get("unavailable") or []
    notes = data.get("notes") or []
    runs = data.get("runs") or []
    extra = [
        "",
        "---",
        "",
        "## Executive notes",
    ]
    if notes:
        for note in notes[:10]:
            title = note.get("title") or note.get("note_type") or "Note"
            body = note.get("body") or ""
            extra.append(f"- **{title}** — {body}")
    else:
        extra.append("- No executive notes captured yet.")

    extra.extend(["", "## Source availability"])
    if unavailable:
        for row in unavailable:
            extra.append(f"- **{row.get('source', 'Source')}**: {row.get('detail') or row.get('status') or 'unavailable'}")
    else:
        extra.append("- No unavailable sources reported.")

    extra.extend(["", "## Run metadata"])
    extra.append(f"- Generated: {datetime.now().isoformat(timespec='seconds')}")
    if runs:
        extra.append(f"- Recent recorded runs: {len(runs)}")

    content = brief.rstrip() + "\n" + "\n".join(extra) + "\n"
    out_path.write_text(content, encoding="utf-8")
    control_center.record_run("digest_script", "ok", summary_path=str(out_path), notes="Generated first-draft Control Center digest")

    print(f"DIGEST_PATH={out_path}")
    print()
    print(content)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
