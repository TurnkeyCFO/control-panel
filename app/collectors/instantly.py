"""Instantly collector — campaigns, warmup accounts, analytics. Read-only."""
import time
import threading
from datetime import date, timedelta
from typing import Any

import httpx

from app import config

_CACHE_TTL = 300
_cache: dict = {}
_lock = threading.Lock()
_BASE = "https://api.instantly.ai/api/v2"


def _key() -> str | None:
    return config.env().get("INSTANTLY_API_KEY")


def _get(path: str, params: dict | None = None) -> Any | None:
    key = _key()
    if not key:
        return None
    r = httpx.get(
        f"{_BASE}{path}",
        params=params,
        headers={"Authorization": f"Bearer {key}"},
        timeout=20,
    )
    r.raise_for_status()
    return r.json()


def _cached(cache_key: str, fn):
    now = time.time()
    with _lock:
        entry = _cache.get(cache_key)
        if entry and now - entry["ts"] < _CACHE_TTL:
            return entry["data"]
    data = fn()
    with _lock:
        _cache[cache_key] = {"ts": now, "data": data}
    return data


def summary() -> dict:
    def _fetch() -> dict:
        out: dict = {
            "connected": False,
            "campaigns": [],
            "accounts": [],
            "totals": {"leads": 0, "sent": 0, "opened": 0, "replied": 0, "bounced": 0},
            "per_campaign": [],
        }
        if not _key():
            return out
        out["connected"] = True

        # Campaigns list
        try:
            r = _get("/campaigns", {"limit": 100, "skip": 0})
            items = (r or {}).get("items") or (r or {}).get("campaigns") or []
            out["campaigns"] = [
                {
                    "id": c.get("id"),
                    "name": c.get("name"),
                    "status": c.get("status"),
                    "created_at": c.get("created_at") or c.get("timestamp"),
                }
                for c in items
            ]
        except Exception as e:
            out["campaigns_error"] = str(e)

        # Campaign analytics (last 30 days)
        start = (date.today() - timedelta(days=30)).isoformat()
        end = date.today().isoformat()
        totals = out["totals"]
        per_campaign = []
        for c in out["campaigns"][:20]:  # cap at 20 to limit API calls
            cid = c.get("id")
            if not cid:
                continue
            try:
                r = _get("/analytics/campaign/summary", {
                    "campaign_id": cid,
                    "start_date": start,
                    "end_date": end,
                })
                stats = r or {}
                sent = int(stats.get("emails_sent_count") or stats.get("total_emails_sent") or 0)
                opened = int(stats.get("unique_open_count") or stats.get("total_open_count") or 0)
                replied = int(stats.get("total_reply_count") or 0)
                bounced = int(stats.get("bounced_count") or 0)
                leads = int(stats.get("total_leads_count") or 0)
                totals["sent"] += sent
                totals["opened"] += opened
                totals["replied"] += replied
                totals["bounced"] += bounced
                totals["leads"] += leads
                per_campaign.append({
                    "id": cid,
                    "name": c.get("name") or cid,
                    "status": c.get("status"),
                    "sent": sent,
                    "opened": opened,
                    "replied": replied,
                    "bounced": bounced,
                    "leads": leads,
                    "open_rate": round(opened / sent * 100, 1) if sent else 0,
                    "reply_rate": round(replied / sent * 100, 2) if sent else 0,
                    "bounce_rate": round(bounced / sent * 100, 2) if sent else 0,
                })
            except Exception:
                per_campaign.append({
                    "id": cid, "name": c.get("name") or cid,
                    "status": c.get("status"),
                    "sent": 0, "opened": 0, "replied": 0,
                    "bounced": 0, "leads": 0,
                    "open_rate": 0, "reply_rate": 0, "bounce_rate": 0,
                })
        # sort by sent desc
        per_campaign.sort(key=lambda x: x["sent"], reverse=True)
        out["per_campaign"] = per_campaign

        # Warmup accounts
        try:
            r = _get("/accounts", {"limit": 100, "skip": 0})
            items = (r or {}).get("items") or (r or {}).get("accounts") or []
            out["accounts"] = [
                {
                    "email": a.get("email"),
                    "warmup_score": (
                        a.get("warmup_score")
                        or (a.get("warmup") or {}).get("score")
                    ),
                    "warmup_enabled": (
                        a.get("warmup_enabled")
                        or (a.get("warmup") or {}).get("enabled")
                    ),
                    "status": a.get("status"),
                    "daily_limit": a.get("daily_limit"),
                }
                for a in items
            ]
        except Exception as e:
            out["accounts_error"] = str(e)

        return out

    return _cached("instantly_summary", _fetch)


def invalidate():
    with _lock:
        _cache.clear()
