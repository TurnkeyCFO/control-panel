"""OpenRouter credit/usage collector. Runs only if OPENROUTER_MANAGEMENT_KEY is present."""
import time

import httpx

from app.util import secrets
from app.db import connect


async def poll() -> dict | None:
    key = secrets.get("OPENROUTER_MANAGEMENT_KEY") or secrets.get("OPENROUTER_API_KEY")
    if not key or key == "****":
        return None
    headers = {"Authorization": f"Bearer {key}"}
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get("https://openrouter.ai/api/v1/credits", headers=headers)
            if r.status_code != 200:
                return None
            data = r.json().get("data", {})
    except Exception:
        return None

    ts = time.time()
    total_credits = data.get("total_credits")
    total_usage = data.get("total_usage")
    with connect() as c:
        for metric, value in (("total_credits", total_credits), ("total_usage", total_usage)):
            if value is None:
                continue
            c.execute(
                "INSERT INTO provider_usage_snapshots (ts, provider, metric, value_usd) VALUES (?,?,?,?)",
                (ts, "openrouter", metric, float(value)),
            )
    return {"total_credits": total_credits, "total_usage": total_usage}
