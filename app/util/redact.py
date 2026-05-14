import re

SECRET_PATTERNS = [
    re.compile(r"sk_live_[A-Za-z0-9]+"),
    re.compile(r"sk-[A-Za-z0-9_\-]{20,}"),
    re.compile(r"pat_[A-Za-z0-9_\-]{20,}"),
    re.compile(r"ghp_[A-Za-z0-9]{30,}"),
    re.compile(r"xoxb-[A-Za-z0-9\-]+"),
    re.compile(r"Bearer\s+[A-Za-z0-9\._\-]+", re.IGNORECASE),
    re.compile(r"(Authorization|api-key|x-api-key)\s*[:=]\s*[\"']?[^\s\"']+", re.IGNORECASE),
]

SENSITIVE_KEYS = {"prompt", "completion", "messages", "content", "body", "response", "input", "output"}


def redact_str(s: str) -> str:
    out = s
    for pat in SECRET_PATTERNS:
        out = pat.sub("***REDACTED***", out)
    return out


def redact_obj(obj):
    if isinstance(obj, dict):
        return {k: ("***REDACTED***" if k.lower() in SENSITIVE_KEYS else redact_obj(v)) for k, v in obj.items()}
    if isinstance(obj, list):
        return [redact_obj(v) for v in obj]
    if isinstance(obj, str):
        return redact_str(obj)
    return obj
