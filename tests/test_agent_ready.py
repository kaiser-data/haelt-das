"""Agent discovery endpoints (robots.txt, llms.txt, markdown, API catalog, agent skills), offline via TestClient."""
import hashlib

from fastapi.testclient import TestClient

from app.server import app

client = TestClient(app, base_url="https://haelt.example")


def test_browser_gets_html_with_discovery_link_header():
    r = client.get("/", headers={"Accept": "text/html,application/xhtml+xml,*/*;q=0.8"})
    assert r.headers["content-type"].startswith("text/html")
    assert 'rel="api-catalog"' in r.headers["link"] and "Accept" in r.headers["vary"]


def test_agent_asking_for_markdown_gets_markdown():
    r = client.get("/", headers={"Accept": "text/markdown, text/html;q=0.5"})
    assert r.headers["content-type"].startswith("text/markdown")
    assert r.text.startswith("# Hält das?") and "POST /api/check" in r.text
    assert int(r.headers["x-markdown-tokens"]) > 0


def test_wildcard_accept_still_gets_html():
    assert client.get("/", headers={"Accept": "*/*"}).headers["content-type"].startswith("text/html")


def test_robots_has_content_signals_ai_bot_rules_and_sitemap():
    body = client.get("/robots.txt").text
    assert "Content-Signal: search=yes, ai-input=yes, ai-train=no" in body
    assert "User-agent: ChatGPT-User" in body and "User-agent: GPTBot" in body
    assert "Sitemap: https://haelt.example/sitemap.xml" in body


def test_sitemap_and_llms_txt_use_the_public_origin():
    assert "<loc>https://haelt.example/</loc>" in client.get("/sitemap.xml").text
    llms = client.get("/llms.txt").text
    assert llms.startswith("# Hält das?\n\n> ") and "https://haelt.example/index.md" in llms


def test_forwarded_proto_from_the_tunnel_is_honoured():
    plain = TestClient(app, base_url="http://haelt.example")
    body = plain.get("/robots.txt", headers={"X-Forwarded-Proto": "https"}).text
    assert "Sitemap: https://haelt.example/sitemap.xml" in body


def test_api_catalog_is_a_linkset_pointing_to_the_openapi_description():
    r = client.get("/.well-known/api-catalog")
    assert r.headers["content-type"].startswith("application/linkset+json")
    entry = r.json()["linkset"][0]
    assert entry["service-desc"][0]["href"] == "https://haelt.example/openapi.json"
    assert client.head("/.well-known/api-catalog").status_code == 200
    spec = client.get("/openapi.json").json()
    assert "requestBody" in spec["paths"]["/api/check"]["post"]


def test_agent_skill_digest_matches_the_served_file():
    skill = client.get("/.well-known/agent-skills/index.json").json()["skills"][0]
    served = client.get(skill["url"].replace("https://haelt.example", ""))
    assert served.content.startswith(b"---\nname: haelt-das") or served.content.startswith(b"---\r\nname: haelt-das")
    assert skill["digest"] == "sha256:" + hashlib.sha256(served.content).hexdigest()
