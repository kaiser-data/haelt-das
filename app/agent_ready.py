"""Discovery for AI agents and crawlers: robots.txt with Content Signals, sitemap, llms.txt, markdown versions of the
home page, an RFC 9727 API catalog and an Agent Skills index. Only what the app really offers is advertised: no MCP
server, OAuth or payments, so none of those are announced."""
import hashlib
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, PlainTextResponse, Response

AGENT = Path(__file__).resolve().parent.parent / "web" / "agent"
SKILL = "haelt-das"
SKILL_PATH = f"/.well-known/agent-skills/{SKILL}/SKILL.md"
SKILL_DESCRIPTION = ("Check whether a product listing is worth buying and get a BUY / AVOID / BUY_ALTERNATIVE / ASK "
                     "verdict with sources and a cost per day.")
REPO = "https://github.com/kaiser-data/haelt-das"

# Search and user-triggered agents may read the site; model-training crawlers may not (matches ai-train=no).
AGENT_BOTS = ("OAI-SearchBot", "ChatGPT-User", "Claude-SearchBot", "Claude-User", "PerplexityBot", "Perplexity-User",
              "Google-CloudVertexBot", "DuckAssistBot", "MistralAI-User")
TRAINING_BOTS = ("GPTBot", "ClaudeBot", "CCBot", "Google-Extended", "Applebot-Extended", "meta-externalagent",
                 "Bytespider")
CONTENT_SIGNAL = "search=yes, ai-input=yes, ai-train=no"

LINK_HEADER = ", ".join((
    '</.well-known/api-catalog>; rel="api-catalog"',
    '</openapi.json>; rel="service-desc"; type="application/openapi+json"',
    '</index.md>; rel="alternate"; type="text/markdown"',
    '</llms.txt>; rel="describedby"; type="text/markdown"',
))

router = APIRouter(include_in_schema=False)


def base_url(req: Request):
    """Public origin of this request, honouring the proxy headers set by the tunnel / reverse proxy."""
    proto = req.headers.get("x-forwarded-proto", req.url.scheme).split(",")[0].strip()
    host = req.headers.get("x-forwarded-host") or req.headers.get("host") or req.url.netloc
    return f"{proto}://{host.split(',')[0].strip()}"


def _q(accept, media):
    """Quality value the Accept header gives this media type (exact or wildcard match), 0 if absent."""
    best = 0.0
    for part in (accept or "").split(","):
        bits = [b.strip() for b in part.split(";")]
        kind = bits[0].lower()
        if kind not in (media, media.split("/")[0] + "/*", "*/*"):
            continue
        q = 1.0
        for b in bits[1:]:
            if b.lower().startswith("q="):
                try:
                    q = float(b[2:])
                except ValueError:
                    q = 0.0
        # an exact type outranks a wildcard at the same q
        best = max(best, q + (0.001 if kind == media else 0))
    return best


def wants_markdown(req: Request):
    """Markdown only when the client names text/markdown itself; '*/*' (browsers, curl) keeps the HTML app."""
    accept = req.headers.get("accept", "")
    if "text/markdown" not in accept.lower():
        return False
    md = _q(accept, "text/markdown")
    return md > 0 and md >= _q(accept, "text/html")


def _overview():
    return (AGENT / "index.md").read_text(encoding="utf-8")


def markdown_response(req: Request):
    body = _overview()
    if req.method == "HEAD":
        body = ""
    return Response(body, media_type="text/markdown; charset=utf-8",
                    headers={"Vary": "Accept", "Link": LINK_HEADER,
                             "X-Markdown-Tokens": str(len(_overview()) // 4)})


@router.api_route("/index.md", methods=["GET", "HEAD"])
async def index_md(req: Request):
    return markdown_response(req)


@router.api_route("/llms.txt", methods=["GET", "HEAD"])
async def llms_txt(req: Request):
    b = base_url(req)
    body = "\n".join((
        "# Hält das?",
        "",
        "> Checks a product listing (link, text or screenshot) the way an experienced buyer would: real shops, specs "
        "that add up, clones, failure reports, the official French durability index and cost per day. Returns BUY, "
        "AVOID, BUY_ALTERNATIVE or ASK with a source for every reason.",
        "",
        "Agents call `POST /api/check` with JSON `{\"text\": ...}`, `{\"url\": ...}` or `{\"image\": ...}` and read the "
        "Server-Sent Events stream until `{\"type\": \"end\"}`.",
        "",
        "## Docs",
        f"- [Overview and API]({b}/index.md): what is checked, request and response format, limits",
        f"- [Agent skill]({b}{SKILL_PATH}): how an agent should call the check and report the verdict",
        f"- [OpenAPI]({b}/openapi.json): machine-readable API description",
        "",
        "## Optional",
        f"- [Source code]({REPO}): FastAPI app, rules, tests",
        "",
    ))
    return Response("" if req.method == "HEAD" else body, media_type="text/markdown; charset=utf-8")


@router.api_route("/robots.txt", methods=["GET", "HEAD"])
async def robots_txt(req: Request):
    lines = ["# Hält das? Agents welcome; overview for language models: /llms.txt",
             "# Content Signals: https://contentsignals.org/", "",
             "User-agent: *", f"Content-Signal: {CONTENT_SIGNAL}", "Allow: /", "Disallow: /api/", ""]
    for bot in AGENT_BOTS:
        lines += [f"User-agent: {bot}"]
    lines += [f"Content-Signal: {CONTENT_SIGNAL}", "Allow: /", "Disallow: /api/", ""]
    for bot in TRAINING_BOTS:
        lines += [f"User-agent: {bot}"]
    lines += ["Disallow: /", "", f"Sitemap: {base_url(req)}/sitemap.xml", ""]
    return PlainTextResponse("" if req.method == "HEAD" else "\n".join(lines))


@router.api_route("/sitemap.xml", methods=["GET", "HEAD"])
async def sitemap_xml(req: Request):
    b = base_url(req)
    urls = "".join(f"<url><loc>{b}{p}</loc></url>" for p in ("/", "/index.md", "/llms.txt", SKILL_PATH))
    body = ('<?xml version="1.0" encoding="UTF-8"?>\n'
            f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>\n')
    return Response("" if req.method == "HEAD" else body, media_type="application/xml")


@router.api_route("/.well-known/api-catalog", methods=["GET", "HEAD"])
async def api_catalog(req: Request):
    """RFC 9727 API catalog as an RFC 9264 linkset."""
    b = base_url(req)
    linkset = {"linkset": [{
        "anchor": f"{b}/api",
        "service-desc": [{"href": f"{b}/openapi.json", "type": "application/openapi+json"}],
        "service-doc": [{"href": f"{b}/index.md", "type": "text/markdown"},
                        {"href": f"{b}/docs", "type": "text/html"}],
        "describedby": [{"href": f"{b}{SKILL_PATH}", "type": "text/markdown"}],
    }]}
    headers = {"Link": f'<{b}/.well-known/api-catalog>; rel="api-catalog"'}
    if req.method == "HEAD":
        return Response(media_type="application/linkset+json", headers=headers)
    return JSONResponse(linkset, media_type="application/linkset+json", headers=headers)


def _skill_bytes():
    return (AGENT / "SKILL.md").read_bytes()


@router.api_route("/.well-known/agent-skills/index.json", methods=["GET", "HEAD"])
async def agent_skills_index(req: Request):
    """Agent Skills Discovery index (Cloudflare RFC draft v0.2.0)."""
    index = {
        "$schema": "https://schemas.agentskills.io/discovery/0.2.0/schema.json",
        "skills": [{"name": SKILL, "type": "skill-md", "description": SKILL_DESCRIPTION,
                    "url": f"{base_url(req)}{SKILL_PATH}",
                    "digest": "sha256:" + hashlib.sha256(_skill_bytes()).hexdigest()}],
    }
    if req.method == "HEAD":
        return Response(media_type="application/json")
    return JSONResponse(index)


@router.api_route(SKILL_PATH, methods=["GET", "HEAD"])
async def skill_md(req: Request):
    # served byte for byte, so the digest in the index matches
    return Response(b"" if req.method == "HEAD" else _skill_bytes(), media_type="text/markdown; charset=utf-8")
