"""Optional persistence to Supabase (PostgREST). Active only when SUPABASE_URL and SUPABASE_SERVICE_KEY are set."""
import os

import httpx

_client = httpx.AsyncClient(timeout=20)


async def save_check(inp, claim, found, flags, clones, life, cost, verdict, calls):
    url, key = os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_SERVICE_KEY")
    if not (url and key):
        return None
    kind = next((k for k in ("page", "image", "url", "text") if inp.get(k)), "text")
    ref = inp.get("url") or (inp.get("page") or {}).get("url") or (inp.get("text") or "")[:300] or None
    me = (cost.get("rows") or [{}])[0]
    row = {
        "input_kind": kind, "input_ref": ref,
        "title": claim.get("title"), "brand": claim.get("brand"), "category": claim.get("category"),
        "price_eur": claim.get("price_eur"),
        "verdict": verdict.get("verdict"), "confidence": verdict.get("confidence"), "headline": verdict.get("headline"),
        "cost_per_day": (me.get("per_day") or {}).get("mid"),
        "life_low_y": (me.get("life_years") or {}).get("low"), "life_high_y": (me.get("life_years") or {}).get("high"),
        "n_spec_flags": len(flags), "n_failures": len([r for r in life.get("reports", []) if r.get("failure")]),
        "n_brands": len(clones.get("brands") or []),
        "claim": claim, "idealo": found, "spec_flags": flags, "clones": clones, "lifetime": life, "cost": cost,
        "verdict_full": verdict, "nebius_calls": calls,
    }
    try:
        headers = {"apikey": key, "Prefer": "return=representation"}
        if not key.startswith("sb_"):  # legacy service_role JWT also goes in Authorization; new sb_secret_ keys do not
            headers["Authorization"] = f"Bearer {key}"
        r = await _client.post(f"{url}/rest/v1/checks", json=row, headers=headers)
        r.raise_for_status()
        return r.json()[0]["id"]
    except Exception as e:  # noqa: BLE001 - a storage outage must never break a live check
        print("supabase save failed:", e)
        return None
