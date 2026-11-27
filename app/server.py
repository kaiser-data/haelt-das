"""FastAPI server: POST /api/check streams pipeline events as Server-Sent Events; / serves the website."""
import asyncio
import json
import logging
import re
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from fastapi import FastAPI, HTTPException, Request  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import FileResponse, StreamingResponse  # noqa: E402

from app import pipeline  # noqa: E402

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


@app.get("/")
async def index():
    return FileResponse(WEB / "index.html")


# Installable app (PWA): manifest with a share target, service worker at the root scope, icons
@app.get("/manifest.webmanifest")
async def manifest():
    return FileResponse(WEB / "manifest.webmanifest", media_type="application/manifest+json")


@app.get("/sw.js")
async def service_worker():
    return FileResponse(WEB / "sw.js", media_type="text/javascript", headers={"Cache-Control": "no-cache"})


ICONS = {p.name: p for p in (WEB / "icons").glob("*.png")}


@app.get("/icons/{name}")
async def icon(name: str):
    if name not in ICONS:  # only the files that exist at startup, never a path from the request
        raise HTTPException(status_code=404)
    return FileResponse(ICONS[name], media_type="image/png")


def _tokens(text):
    return set(re.findall(r"[a-z0-9äöüß]+", (text or "").lower()))


def _find_recording(text):
    """The saved live run whose input matches this text best (token overlap), or None."""
    want, best, best_score = _tokens(text), None, 0.0
    for path in SAMPLES.glob("*.json"):
        rec = json.loads(path.read_text(encoding="utf-8"))
        inp = rec.get("input")
        have = _tokens(inp if isinstance(inp, str) else json.dumps(inp))
        score = len(want & have) / max(len(want | have), 1)
        if score > best_score:
            best, best_score = rec, score
    return best if best_score >= 0.5 else None


@app.post("/api/replay")
async def replay(req: Request):
    """Demo recording mode: stream a saved live run (samples/batch) with the same events, at a recordable pace."""
    inp = await req.json()
    rec = await asyncio.to_thread(_find_recording, inp.get("text") or "")

    async def stream():
        if rec is None:
            yield f"data: {json.dumps({'type': 'error', 'message': 'No recorded run for this input; use a live check.'})}\n\n"
        else:
            for ev in rec["events"]:
                kind = ev.get("status") if ev.get("status") == "running" else ev.get("type")
                await asyncio.sleep(REPLAY_PACE.get(kind, 0.3))
                yield f"data: {json.dumps(ev, ensure_ascii=False, default=str)}\n\n"
        yield "data: {\"type\": \"end\"}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.post("/api/check")
async def check(req: Request):
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
