"""Minimal idealo MCP client: OAuth (DCR + PKCE, loopback) and JSON-RPC tool calls.

Usage:
  python3 scripts/idealo_mcp.py login              # opens browser, stores token in .idealo_token.json
  python3 scripts/idealo_mcp.py tools              # list tools
  python3 scripts/idealo_mcp.py call <tool> '<json-args>'
"""
import base64
import hashlib
import http.server
import json
import secrets
import sys
import threading
import time
import urllib.parse
import urllib.request
import webbrowser
from pathlib import Path

BASE = "https://mcp.idealo.com"
MCP_URL = f"{BASE}/mcp"
SCOPE = "openid email profile https://mcp.idealo.com/mcp/api.full-access"
PORT = 6274
REDIRECT = f"http://localhost:{PORT}/callback"
TOKEN_FILE = Path(__file__).resolve().parent.parent / ".idealo_token.json"


def _post(url, data, headers=None, form=True):
    body = urllib.parse.urlencode(data).encode() if form else json.dumps(data).encode()
    h = {"Content-Type": "application/x-www-form-urlencoded" if form else "application/json"}
    h.update(headers or {})
    req = urllib.request.Request(url, data=body, headers=h, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, dict(r.headers), r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read().decode()


def login():
    status, _, body = _post(f"{BASE}/oauth2/register", {
        "client_name": "hackathon-agent",
        "redirect_uris": [REDIRECT],
        "grant_types": ["authorization_code", "refresh_token"],
        "response_types": ["code"],
        "token_endpoint_auth_method": "none",
        "scope": SCOPE,
    }, form=False)
    if status >= 300:
        sys.exit(f"register failed {status}: {body}")
    client_id = json.loads(body)["client_id"]

    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    state = secrets.token_urlsafe(16)
    result = {}

    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            result.update({k: v[0] for k, v in q.items()})
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Login done. You can close this tab.")

        def log_message(self, *a):
            pass

    srv = http.server.HTTPServer(("localhost", PORT), H)
    threading.Thread(target=srv.handle_request, daemon=True).start()
    url = f"{BASE}/oauth2/authorize?" + urllib.parse.urlencode({
        "response_type": "code", "client_id": client_id, "redirect_uri": REDIRECT,
        "scope": SCOPE, "state": state, "code_challenge": challenge,
        "code_challenge_method": "S256", "resource": MCP_URL,
    })
    print("Opening browser for idealo login...\n" + url)
    webbrowser.open(url)
    for _ in range(300):
        if result:
            break
        time.sleep(1)
    if result.get("state") != state or "code" not in result:
        sys.exit(f"auth failed: {result}")
    status, _, body = _post(f"{BASE}/oauth2/token", {
        "grant_type": "authorization_code", "code": result["code"], "redirect_uri": REDIRECT,
        "client_id": client_id, "code_verifier": verifier, "resource": MCP_URL,
    })
    if status >= 300:
        sys.exit(f"token failed {status}: {body}")
    tok = json.loads(body)
    tok["client_id"] = client_id
    tok["obtained_at"] = int(time.time())
    TOKEN_FILE.write_text(json.dumps(tok, indent=2))
    TOKEN_FILE.chmod(0o600)
    print("token stored; scopes:", tok.get("scope"))


def _token():
    tok = json.loads(TOKEN_FILE.read_text())
    if time.time() > tok["obtained_at"] + tok.get("expires_in", 3600) - 60 and tok.get("refresh_token"):
        status, _, body = _post(f"{BASE}/oauth2/token", {
            "grant_type": "refresh_token", "refresh_token": tok["refresh_token"],
            "client_id": tok["client_id"],
        })
        if status < 300:
            new = json.loads(body)
            tok.update(new, obtained_at=int(time.time()))
            TOKEN_FILE.write_text(json.dumps(tok, indent=2))
    return tok["access_token"]


_session = {}


def rpc(method, params=None, notify=False):
    headers = {
        "Authorization": f"Bearer {_token()}",
        "Accept": "application/json, text/event-stream",
        "MCP-Protocol-Version": "2025-06-18",
    }
    if "sid" in _session:
        headers["Mcp-Session-Id"] = _session["sid"]
    msg = {"jsonrpc": "2.0", "method": method, "params": params or {}}
    if not notify:
        msg["id"] = secrets.randbelow(10**9)
    status, h, body = _post(MCP_URL, msg, headers, form=False)
    sid = h.get("Mcp-Session-Id") or h.get("mcp-session-id")
    if sid:
        _session["sid"] = sid
    if status >= 300:
        raise RuntimeError(f"{method} -> HTTP {status}: {body[:500]}")
    if notify or not body.strip():
        return None
    if body.lstrip().startswith("event:") or body.lstrip().startswith("data:"):
        datas = [ln[5:].strip() for ln in body.splitlines() if ln.startswith("data:")]
        body = datas[-1]
    return json.loads(body)


def connect():
    rpc("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                       "clientInfo": {"name": "hackathon-agent", "version": "0.1"}})
    rpc("notifications/initialized", notify=True)


def call(tool, args):
    connect()
    return rpc("tools/call", {"name": tool, "arguments": args})


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "tools"
    if cmd == "login":
        login()
    elif cmd == "tools":
        connect()
        res = rpc("tools/list")
        for t in res["result"]["tools"]:
            print(t["name"], "-", (t.get("description") or "")[:100])
    elif cmd == "call":
        print(json.dumps(call(sys.argv[2], json.loads(sys.argv[3])), indent=2, ensure_ascii=False)[:6000])
