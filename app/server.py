"""FastAPI server: POST /api/check streams pipeline events as Server-Sent Events; / serves the website."""
import asyncio
import json
import logging
import os
import re
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from fastapi import FastAPI, HTTPException, Request, status  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import FileResponse, StreamingResponse  # noqa: E402

from app import agent_ready, pipeline  # noqa: E402

log = logging.getLogger("app.server")


def _configure_app_logging():
    """Send our own 'app.*' loggers to stderr under uvicorn; the root logger stays untouched for importers."""
    app_log = logging.getLogger("app")
    if not app_log.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
        app_log.addHandler(handler)
        app_log.setLevel(logging.INFO)


_configure_app_logging()

WEB = Path(__file__).resolve().parent.parent / "web"
SAMPLES = Path(__file__).resolve().parent.parent / "samples" / "batch"
# Seconds between replayed events: fast enough to record, slow enough to follow.
REPLAY_PACE = {"running": 0.35, "step": 0.7, "calls": 0.25, "verdict": 0.9}
app = FastAPI(title="Hält das?")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.include_router(agent_ready.router)  # robots.txt, sitemap, llms.txt, API catalog, agent skills


@app.head("/", include_in_schema=False)
@app.get("/", status_code=status.HTTP_200_OK, summary="The web app")
async def index(req: Request):
    """The web app, or its markdown overview when the client prefers text/markdown (agents)."""
    if agent_ready.wants_markdown(req):
        return agent_ready.markdown_response(req)
    return FileResponse(WEB / "index.html", headers={"Vary": "Accept", "Link": agent_ready.LINK_HEADER})


# Installable app (PWA): manifest with a share target, service worker at the root scope, icons
@app.get("/manifest.webmanifest", status_code=status.HTTP_200_OK, summary="PWA manifest with share target")
async def manifest():
    return FileResponse(WEB / "manifest.webmanifest", media_type="application/manifest+json")


@app.get("/sw.js", status_code=status.HTTP_200_OK, summary="Service worker (app shell cache)")
async def service_worker():
    return FileResponse(WEB / "sw.js", media_type="text/javascript", headers={"Cache-Control": "no-cache"})


ICONS = {p.name: p for p in (WEB / "icons").glob("*.png")}


@app.get("/icons/{name}", status_code=status.HTTP_200_OK, summary="App icons")
async def icon(name: str):
    if name not in ICONS:  # only the files that exist at startup, never a path from the request
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return FileResponse(ICONS[name], media_type="image/png")


def _tokens(text):
    return set(re.findall(r"[a-z0-9äöüß]+", (text or "").lower()))


REPLAY_MIN_MATCH = 0.75  # token overlap needed to reuse a recording; an edited listing must not borrow another's result
# Public demo link: no live checks (they spend API credits); recorded examples only
REPLAY_ONLY = os.environ.get("HAELTDAS_REPLAY_ONLY") == "1"


def _load_recording(path):
    try:
        rec = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        log.warning("skipping unreadable recording %s: %s", path.name, e)
        return None
    return rec if isinstance(rec.get("events"), list) else None


def _find_recording(text):
    """The saved live run whose input matches this text (token overlap >= REPLAY_MIN_MATCH), or None."""
    want, best, best_score = _tokens(text), None, 0.0
    for path in SAMPLES.glob("*.json"):
        rec = _load_recording(path)
        if rec is None:
            continue
        inp = rec.get("input")
        have = _tokens(inp if isinstance(inp, str) else json.dumps(inp))
        if {t for t in want if t.isdigit()} - have:  # a different price or spec is a different listing
            continue
        score = len(want & have) / max(len(want | have), 1)
        if score > best_score:
            best, best_score = rec, score
    return best if best_score >= REPLAY_MIN_MATCH else None


def _sse(ev):
    return f"data: {json.dumps(ev, ensure_ascii=False, default=str)}\n\n"


async def _replay_stream(inp):
    text = inp.get("text") if isinstance(inp, dict) else None
    if not isinstance(text, str) or not text.strip():
        yield _sse({"type": "error", "message": "Replay works for the example listings only (pick a chip). Links, "
                                                "screenshots and pages need a live check."})
    else:
        rec = await asyncio.to_thread(_find_recording, text)
        if rec is None:
            yield _sse({"type": "error", "message": "No recorded run for this listing. Pick one of the examples."})
        else:
            original = rec["input"] if isinstance(rec["input"], str) else json.dumps(rec["input"], ensure_ascii=False)
            yield _sse({"type": "step", "id": "replay", "status": "done",
                        "title": f"Recorded live run (27 Nov 2026), replayed faster: {original[:90]}"})
            for ev in rec["events"]:
                kind = ev.get("status") if ev.get("status") == "running" else ev.get("type")
                await asyncio.sleep(REPLAY_PACE.get(kind, 0.3))
                yield _sse(ev)
    yield _sse({"type": "end"})


CHECK_OPENAPI = {
    "requestBody": {"required": True, "content": {"application/json": {"schema": {
        "type": "object",
        "description": "One of text, url or image.",
        "properties": {"text": {"type": "string", "description": "Listing text"},
                       "url": {"type": "string", "format": "uri", "description": "Product page URL"},
                       "image": {"type": "string", "description": "Screenshot as a data: URL"}}}}}},
    "responses": {"200": {"description": "Server-Sent Events; JSON events with a 'type' "
                                         "(step, calls, verdict, saved, error), ending with {\"type\": \"end\"}",
                          "content": {"text/event-stream": {"schema": {"type": "string"}}}}},
}


@app.post("/api/replay", status_code=status.HTTP_200_OK, summary="Replay a recorded live run as SSE",
          openapi_extra=CHECK_OPENAPI)
async def replay(req: Request):
    """Demo recording mode: stream a saved live run (samples/batch) with the same events, at a recordable pace."""
    try:
        inp = await req.json()
    except ValueError:
        inp = None
    return StreamingResponse(_replay_stream(inp), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.post("/api/check", status_code=status.HTTP_200_OK, summary="Check a listing live, streamed as SSE",
          openapi_extra=CHECK_OPENAPI)
async def check(req: Request):
    if REPLAY_ONLY:
        return await replay(req)
    inp = await req.json()

    async def stream():
        try:
            async for ev in pipeline.run(inp):
                yield f"data: {json.dumps(ev, ensure_ascii=False, default=str)}\n\n"
        except Exception as e:  # noqa: BLE001 - surface the error in the UI instead of a dead stream
            log.exception("check failed for input kinds %s", sorted(k for k in inp if inp.get(k)))
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
        yield "data: {\"type\": \"end\"}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
