"""HubSpot collector — contacts, cold-dial pipeline, deals. Read-only."""
import time
import threading
from typing import Any

import httpx

from app import config

_CACHE_TTL = 300
_cache: dict = {}
_lock = threading.Lock()
_BASE = "https://api.hubapi.com"


def _token() -> str | None:
    return config.env().get("HUBSPOT_PRIVATE_APP_TOKEN")


def _headers() -> dict:
    tok = _token()
    if not tok:
        return {}
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


def _get(path: str, params: dict | None = None) -> Any | None:
    tok = _token()
    if not tok:
        return None
    r = httpx.get(f"{_BASE}{path}", params=params, headers=_headers(), timeout=15)
    r.raise_for_status()
    return r.json()


def _search(object_type: str, body: dict) -> Any | None:
    tok = _token()
    if not tok:
        return None
    r = httpx.post(
        f"{_BASE}/crm/v3/objects/{object_type}/search",
        json=body,
        headers=_headers(),
        timeout=15,
    )
    r.raise_for_status()
    return r.json()


def _cached(key: str, fn):
    now = time.time()
    with _lock:
        entry = _cache.get(key)
        if entry and now - entry["ts"] < _CACHE_TTL:
            return entry["data"]
    data = fn()
    with _lock:
        _cache[key] = {"ts": now, "data": data}
    return data


def _count(object_type: str, filters: list | None = None) -> int:
    body: dict = {"filterGroups": [], "limit": 1}
    if filters:
        body["filterGroups"] = [{"filters": filters}]
    r = _search(object_type, body)
    return (r or {}).get("total", 0)


def summary() -> dict:
    def _fetch() -> dict:
        out: dict = {
            "connected": False,
            "contacts": {},
            "cold_dial": {},
            "deals": {},
            "recent_contacts": [],
            "deal_pipeline": [],
        }
        if not _token():
            return out
        out["connected"] = True

        # total contacts
        try:
            out["contacts"]["total"] = _count("contacts")
        except Exception as e:
            out["contacts"]["error"] = str(e)

        # lifecycle stage breakdown
        STAGES = [
            "subscriber", "lead", "marketingqualifiedlead",
            "salesqualifiedlead", "opportunity", "customer",
        ]
        by_stage = {}
        for stage in STAGES:
            try:
                by_stage[stage] = _count(
                    "contacts",
                    [{"propertyName": "lifecyclestage", "operator": "EQ", "value": stage}],
                )
            except Exception:
                pass
        out["contacts"]["by_stage"] = by_stage

        # cold-dial stats
        try:
            out["cold_dial"]["retry_queue"] = _count(
                "contacts",
                [{"propertyName": "ct_next_call_date", "operator": "HAS_PROPERTY"}],
            )
        except Exception:
            pass
        try:
            out["cold_dial"]["do_not_call"] = _count(
                "contacts",
                [{"propertyName": "ct_do_not_call", "operator": "EQ", "value": "true"}],
            )
        except Exception:
            pass
        try:
            out["cold_dial"]["wrong_number"] = _count(
                "contacts",
                [{"propertyName": "ct_wrong_number", "operator": "EQ", "value": "true"}],
            )
        except Exception:
            pass

        # deals total
        try:
            out["deals"]["total"] = _count("deals")
        except Exception as e:
            out["deals"]["error"] = str(e)

        # deal pipeline breakdown
        try:
            r = _search("deals", {
                "filterGroups": [],
                "properties": ["dealstage", "amount", "dealname", "closedate"],
                "sorts": [{"propertyName": "createdate", "direction": "DESCENDING"}],
                "limit": 200,
            })
            stage_agg: dict = {}
            for deal in (r or {}).get("results", []):
                props = deal.get("properties", {})
                stage = props.get("dealstage") or "unknown"
                amount = float(props.get("amount") or 0)
                if stage not in stage_agg:
                    stage_agg[stage] = {"count": 0, "amount": 0.0, "deals": []}
                stage_agg[stage]["count"] += 1
                stage_agg[stage]["amount"] += amount
                stage_agg[stage]["deals"].append({
                    "name": props.get("dealname") or "—",
                    "amount": amount,
                    "close": props.get("closedate") or "",
                })
            out["deal_pipeline"] = [
                {"stage": k, **v} for k, v in stage_agg.items()
            ]
        except Exception as e:
            out["deals"]["pipeline_error"] = str(e)

        # recent contacts
        try:
            r = _search("contacts", {
                "filterGroups": [],
                "properties": ["firstname", "lastname", "email", "lifecyclestage", "createdate", "ct_next_call_date"],
                "sorts": [{"propertyName": "createdate", "direction": "DESCENDING"}],
                "limit": 25,
            })
            out["recent_contacts"] = [
                {
                    "id": c["id"],
                    "name": f"{c['properties'].get('firstname') or ''} {c['properties'].get('lastname') or ''}".strip()
                            or c["properties"].get("email") or "—",
                    "email": c["properties"].get("email") or "",
                    "stage": c["properties"].get("lifecyclestage") or "",
                    "created": c["properties"].get("createdate") or "",
                    "next_call": c["properties"].get("ct_next_call_date") or "",
                }
                for c in (r or {}).get("results", [])
            ]
        except Exception as e:
            out["contacts"]["recent_error"] = str(e)

        return out

    return _cached("hubspot_summary", _fetch)


def invalidate():
    with _lock:
        _cache.clear()
