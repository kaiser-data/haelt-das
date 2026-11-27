"""Async client for the idealo MCP server (token from scripts/idealo_mcp.py login)."""
import asyncio
import json
import re
import secrets
import time
from pathlib import Path

import httpx

BASE = "https://mcp.idealo.com"
MCP_URL = f"{BASE}/mcp"
TOKEN_FILE = Path(__file__).resolve().parent.parent / ".idealo_token.json"

CONNECT_TIMEOUT = 5  # a dead host shows up in seconds; only reading the answer may take long
_client = httpx.AsyncClient(timeout=httpx.Timeout(60, connect=CONNECT_TIMEOUT))
_state = {"sid": None, "calls": 0}


async def _token():
    tok = json.loads(await asyncio.to_thread(TOKEN_FILE.read_text, encoding="utf-8"))
    if time.time() > tok["obtained_at"] + tok.get("expires_in", 3600) - 60 and tok.get("refresh_token"):
        r = await _client.post(f"{BASE}/oauth2/token", data={
            "grant_type": "refresh_token", "refresh_token": tok["refresh_token"], "client_id": tok["client_id"],
        })
        if r.status_code < 300:
            tok.update(r.json(), obtained_at=int(time.time()))
            await asyncio.to_thread(TOKEN_FILE.write_text, json.dumps(tok, indent=2), encoding="utf-8")
    return tok["access_token"]


async def _rpc(method, params=None, notify=False):
    headers = {
        "Authorization": f"Bearer {await _token()}",
        "Accept": "application/json, text/event-stream",
        "MCP-Protocol-Version": "2025-06-18",
    }
    if _state["sid"]:
        headers["Mcp-Session-Id"] = _state["sid"]
    msg = {"jsonrpc": "2.0", "method": method, "params": params or {}}
    if not notify:
        msg["id"] = secrets.randbelow(10**9)
    r = await _client.post(MCP_URL, json=msg, headers=headers)
    sid = r.headers.get("mcp-session-id")
    if sid:
        _state["sid"] = sid
    if r.status_code >= 300:
        raise RuntimeError(f"idealo {method} HTTP {r.status_code}: {r.text[:200]}")
    body = r.text
    if notify or not body.strip():
        return None
    if body.lstrip().startswith(("event:", "data:")):
        body = [ln[5:].strip() for ln in body.splitlines() if ln.startswith("data:")][-1]
    return json.loads(body)


async def _ensure_session():
    if _state["sid"]:
        return
    await _rpc("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                              "clientInfo": {"name": "haelt-das", "version": "0.1"}})
    await _rpc("notifications/initialized", notify=True)


async def tool(name, args):
    await _ensure_session()
    _state["calls"] += 1
    try:
        res = await _rpc("tools/call", {"name": name, "arguments": args})
    except RuntimeError:
        _state["sid"] = None
        await _ensure_session()
        res = await _rpc("tools/call", {"name": name, "arguments": args})
    res = res.get("result", res)
    if res.get("structuredContent") is not None:
        return res["structuredContent"]
    text = "".join(c.get("text", "") for c in res.get("content", []))
    try:
        return json.loads(text)
    except ValueError:
        return {"_text": text}


def euro(s):
    """'86,30 €' -> 86.3"""
    if s is None:
        return None
    if isinstance(s, (int, float)):
        return float(s)
    m = re.search(r"([\d\.]+,\d+|\d+)", s.replace(" ", ""))
    if not m:
        return None
    return float(m.group(1).replace(".", "").replace(",", "."))


async def search(query, country="DE"):
    return await tool("search_products", {"query": query, "country": country})


async def details(ref, country="DE"):
    return await tool("get_product_details", {"productRef": ref, "country": country})


async def history(ref, country="DE"):
    return await tool("get_product_price_history", {"productRef": ref, "country": country})
