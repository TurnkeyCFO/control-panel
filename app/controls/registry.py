from dataclasses import dataclass, field
from pathlib import Path

from app import config

WS = config.WORKSPACE_ROOT

FORBIDDEN_WRITE_PATHS = (
    WS / "CLAUDE.md",
    WS / ".claude" / "CLAUDE.md",
    WS / ".claude" / "rules",
    WS / "context",
)


@dataclass(frozen=True)
class SkillSpec:
    id: str
    label: str
    description: str
    argv: tuple[str, ...]
    cwd: Path
    write_action: bool = False
    category: str = "general"


def _skill_tool(skill: str, tool: str) -> Path:
    return WS / ".claude" / "Skills" / skill / "tools" / tool


def _py(skill: str, tool: str) -> tuple[str, ...]:
    return ("python", str(_skill_tool(skill, tool)))


_ALL: list[SkillSpec] = [
    # ── MAINTENANCE ──────────────────────────────────────────────
    SkillSpec(
        id="claude-maintenance-audit",
        label="Maintenance — audit",
        description="Scan CLAUDE.md / rules / skills for drift, bloat, secret leaks. Read-only.",
        argv=_py("claude-maintenance", "audit.py"),
        cwd=WS, category="maintenance", write_action=False,
    ),
    SkillSpec(
        id="claude-maintenance-daily",
        label="Maintenance — daily run",
        description="Full daily audit + digest. Dry-run unless approved.",
        argv=_py("claude-maintenance", "run_daily.py"),
        cwd=WS, category="maintenance", write_action=False,
    ),
    SkillSpec(
        id="claude-maintenance-digest",
        label="Maintenance — send digest",
        description="Send yesterday's audit digest to Slack.",
        argv=_py("claude-maintenance", "send_digest.py"),
        cwd=WS, category="maintenance", write_action=True,
    ),
    SkillSpec(
        id="claude-maintenance-apply",
        label="Maintenance — apply approvals",
        description="Apply approved fixes onto the maintenance branch.",
        argv=_py("claude-maintenance", "apply_approvals.py"),
        cwd=WS, category="maintenance", write_action=True,
    ),

    # ── TKCFO CONTENT ENGINE ────────────────────────────────────
    SkillSpec(
        id="tkcfo-discover",
        label="TKCFO — discover topics",
        description="Monday 8am topic proposals.",
        argv=_py("tkcfo-content-engine", "discover_topics.py"),
        cwd=WS, category="tkcfo-content",
    ),
    SkillSpec(
        id="tkcfo-parse-brand",
        label="TKCFO — parse brand guide",
        description="Refresh brand-lock tokens from style guide.",
        argv=_py("tkcfo-content-engine", "parse_brand_guide.py"),
        cwd=WS, category="tkcfo-content",
    ),
    SkillSpec(
        id="tkcfo-weekly-digest",
        label="TKCFO — weekly digest",
        description="Fri 4pm pipeline telemetry digest.",
        argv=_py("tkcfo-content-engine", "weekly_digest.py"),
        cwd=WS, category="tkcfo-content",
    ),
    SkillSpec(
        id="tkcfo-generate-artifacts",
        label="TKCFO — generate artifacts",
        description="Render all channel artifacts for the active shoot. Write action.",
        argv=_py("tkcfo-content-engine", "generate_artifacts.py"),
        cwd=WS, category="tkcfo-content", write_action=True,
    ),
    SkillSpec(
        id="tkcfo-telegram-bundle",
        label="TKCFO — telegram approval bundle",
        description="Post active shoot bundle to Telegram for approval.",
        argv=_py("tkcfo-content-engine", "telegram_bundle.py"),
        cwd=WS, category="tkcfo-content", write_action=True,
    ),
    SkillSpec(
        id="tkcfo-blotato-post",
        label="TKCFO — Blotato dispatch",
        description="Post approved artifacts to LinkedIn/FB/IG/YouTube. WRITE ACTION.",
        argv=_py("tkcfo-content-engine", "blotato_post.py"),
        cwd=WS, category="tkcfo-content", write_action=True,
    ),
    SkillSpec(
        id="tkcfo-beehiiv-send",
        label="TKCFO — Beehiiv newsletter",
        description="Send approved newsletter. WRITE ACTION.",
        argv=_py("tkcfo-content-engine", "beehiiv_send.py"),
        cwd=WS, category="tkcfo-content", write_action=True,
    ),
    SkillSpec(
        id="tkcfo-blog-push",
        label="TKCFO — blog push",
        description="Commit + push blog post to GitHub. WRITE ACTION.",
        argv=_py("tkcfo-content-engine", "github_blog_push.py"),
        cwd=WS, category="tkcfo-content", write_action=True,
    ),

    # ── FAITHFUL CONTENT ENGINE ─────────────────────────────────
    SkillSpec(
        id="faithful-discover",
        label="FAITHFUL — discover topics",
        description="Monday 8am topic proposals.",
        argv=_py("faithful-content-engine", "discover_topics.py"),
        cwd=WS, category="faithful-content",
    ),
    SkillSpec(
        id="faithful-parse-brand",
        label="FAITHFUL — parse brand guide",
        description="Refresh brand-lock tokens.",
        argv=_py("faithful-content-engine", "parse_brand_guide.py"),
        cwd=WS, category="faithful-content",
    ),
    SkillSpec(
        id="faithful-weekly-digest",
        label="FAITHFUL — weekly digest",
        description="Fri 4pm pipeline digest.",
        argv=_py("faithful-content-engine", "weekly_digest.py"),
        cwd=WS, category="faithful-content",
    ),
    SkillSpec(
        id="faithful-generate-artifacts",
        label="FAITHFUL — generate artifacts",
        description="Render all channel artifacts for the active shoot.",
        argv=_py("faithful-content-engine", "generate_artifacts.py"),
        cwd=WS, category="faithful-content", write_action=True,
    ),
    SkillSpec(
        id="faithful-telegram-bundle",
        label="FAITHFUL — telegram bundle",
        description="Post bundle for approval.",
        argv=_py("faithful-content-engine", "telegram_bundle.py"),
        cwd=WS, category="faithful-content", write_action=True,
    ),
    SkillSpec(
        id="faithful-blotato-post",
        label="FAITHFUL — Blotato dispatch",
        description="Cross-post to social. WRITE ACTION.",
        argv=_py("faithful-content-engine", "blotato_post.py"),
        cwd=WS, category="faithful-content", write_action=True,
    ),
    SkillSpec(
        id="faithful-beehiiv-send",
        label="FAITHFUL — Beehiiv newsletter",
        description="Send approved newsletter. WRITE ACTION.",
        argv=_py("faithful-content-engine", "beehiiv_send.py"),
        cwd=WS, category="faithful-content", write_action=True,
    ),
    SkillSpec(
        id="faithful-blog-push",
        label="FAITHFUL — blog push",
        description="Commit + push blog to GitHub. WRITE ACTION.",
        argv=_py("faithful-content-engine", "github_blog_push.py"),
        cwd=WS, category="faithful-content", write_action=True,
    ),

    # ── BOOKKEEPING SCRAPER ─────────────────────────────────────
    SkillSpec(
        id="bk-scraper-daily",
        label="Bookkeeping scraper — daily run",
        description="Full daily intent scrape + scoring + notify.",
        argv=_py("bookkeeping-intent-scraper", "run_daily.py"),
        cwd=WS, category="lead-gen",
    ),
    SkillSpec(
        id="bk-scraper-setup-sheet",
        label="Bookkeeping scraper — setup sheet",
        description="Initialize the lead tracking Google Sheet.",
        argv=_py("bookkeeping-intent-scraper", "setup_sheet.py"),
        cwd=WS, category="lead-gen", write_action=True,
    ),
    SkillSpec(
        id="bk-scraper-score",
        label="Bookkeeping scraper — score leads",
        description="Score existing leads without re-scraping.",
        argv=_py("bookkeeping-intent-scraper", "score_leads.py"),
        cwd=WS, category="lead-gen",
    ),

    # ── RESEARCH ────────────────────────────────────────────────
    SkillSpec(
        id="research-brief-daily",
        label="Research brief — daily runner",
        description="Generate today's research brief.",
        argv=_py("research-brief", "daily_runner.py"),
        cwd=WS, category="research",
    ),

    # ── BILL PAY ────────────────────────────────────────────────
    SkillSpec(
        id="bill-pay-cron",
        label="Bill Pay — run cron",
        description="Sync bills to QBO for all clients. WRITE ACTION.",
        argv=("python", str(WS / "businesses" / "turnkey" / "turnkey-cfo" / "bill-pay-automation" / "bill_pay_cron.py")),
        cwd=WS / "businesses" / "turnkey" / "turnkey-cfo" / "bill-pay-automation",
        category="bill-pay", write_action=True,
    ),
]

SKILLS: dict[str, SkillSpec] = {s.id: s for s in _ALL}


# ── VIEW-ONLY SKILLS (no direct Python entrypoint; invoked via Claude Code CLI) ──
VIEW_ONLY_SKILLS = [
    ("approval-worker", "productivity", "Handle approval queues, intake validation, execution gating."),
    ("canvas-design", "creative", "Create visual art in PNG/PDF with design philosophy."),
    ("dashboard-builder", "client-delivery", "Build branded TurnkeyCFO financial dashboards."),
    ("file-organizer", "productivity", "Organize files, find duplicates, restructure projects."),
    ("firecrawl", "research", "Fast web scraping, search, interaction tools."),
    ("frontend-design", "creative", "Production-grade frontend interfaces."),
    ("industry-site-builder", "client-delivery", "Templated industry websites for prospect outreach."),
    ("morning-brief", "productivity", "Daily inbox/calendar/CRM digest + day plan."),
    ("onboarding-checklist", "client-delivery", "Client onboarding workflow."),
    ("self-improving-agent", "meta", "Log failures / corrections / recurring patterns."),
    ("seo-optimizer", "creative", "Keyword research, technical SEO, Core Web Vitals."),
    ("session-handoff", "meta", "End-of-session handoff summaries."),
    ("skill-builder", "meta", "Create/optimize/audit skills."),
    ("usps-status-assistant", "productivity", "Handle USPS status emails + weekly queue."),
    ("video-to-website", "creative", "Scroll-driven animated website from video."),
    ("xlsx", "productivity", "Excel / CSV / TSV read / edit / create."),
]


def list_skills() -> list[dict]:
    return [
        {
            "id": s.id,
            "label": s.label,
            "description": s.description,
            "write_action": s.write_action,
            "category": s.category,
            "view_only": False,
        }
        for s in _ALL
    ] + [
        {
            "id": f"view-only:{name}",
            "label": name,
            "description": desc,
            "write_action": False,
            "category": cat,
            "view_only": True,
        }
        for name, cat, desc in VIEW_ONLY_SKILLS
    ]


def get(skill_id: str) -> SkillSpec | None:
    return SKILLS.get(skill_id)
