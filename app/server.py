"""FastAPI server: POST /api/check streams pipeline events as Server-Sent Events; / serves the website."""
import json
import traceback
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from fastapi import FastAPI, Request  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import FileResponse, StreamingResponse  # noqa: E402

from app import pipeline  # noqa: E402

WEB = Path(__file__).resolve().parent.parent / "web"
app = FastAPI(title="Hält das?")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.get("/")
async def index():
    return FileResponse(WEB / "index.html")


@app.post("/api/check")
async def check(req: Request):
    inp = await req.json()

    async def stream():
        try:
            async for ev in pipeline.run(inp):
                yield f"data: {json.dumps(ev, ensure_ascii=False, default=str)}\n\n"
        except Exception as e:  # noqa: BLE001 - surface the error in the UI instead of a dead stream
            traceback.print_exc()
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
        yield "data: {\"type\": \"end\"}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
