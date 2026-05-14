"""Keys-only parser. Values are NEVER read into memory, logged, or returned."""
import re
from app import config

_KEY_RE = re.compile(r"^\s*(?:export\s+)?([A-Z_][A-Z0-9_]*)\s*=")


PROVIDER_MAP = {
    "OPENROUTER": "openrouter",
    "ANTHROPIC": "anthropic",
    "OPENAI": "openai",
    "BLOTATO": "blotato",
    "BEEHIIV": "beehiiv",
    "FIRECRAWL": "firecrawl",
    "SLACK": "slack",
    "TELEGRAM": "telegram",
    "SUPABASE": "supabase",
    "GITHUB": "github",
    "STRIPE": "stripe",
    "RAMP": "ramp",
    "QB": "quickbooks",
    "GUSTO": "gusto",
    "AZURE": "azure",
    "GOOGLE": "google",
    "RENDER": "render",
    "INSTANTLY": "instantly",
    "APIFY": "apify",
    "APOLLO": "apollo",
    "CLICKUP": "clickup",
    "WINDSOR": "windsor",
    "BRAVE": "brave",
    "CALENDLY": "calendly",
    "RESEND": "resend",
    "ZAPIER": "zapier",
}


def _provider(key: str) -> str:
    for prefix, prov in PROVIDER_MAP.items():
        if key.startswith(prefix):
            return prov
    return "other"


def list_keys() -> list[dict]:
    if not config.ENV_FILE.exists():
        return []
    keys: list[str] = []
    with open(config.ENV_FILE, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            m = _KEY_RE.match(line)
            if m:
                keys.append(m.group(1))
    seen = set()
    out = []
    for k in keys:
        if k in seen:
            continue
        seen.add(k)
        out.append({"key": k, "provider": _provider(k), "present": True})
    return out
