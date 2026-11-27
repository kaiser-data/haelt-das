"""Load saved batch results (samples/batch/*.json) into Supabase public.checks."""
import asyncio
import json
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()
from app import store  # noqa: E402

BATCH_DIR = Path("samples/batch")


def last(events, sid, default):
    data = [e.get("data") for e in events if e.get("type") == "step" and e.get("id") == sid and e.get("data") is not None]
    return data[-1] if data else default


def load_checks():
    """Read every saved run up front (plain file I/O, outside the event loop)."""
    return [(path, json.loads(path.read_text(encoding="utf-8"))) for path in sorted(BATCH_DIR.glob("*.json"))]


async def save_all(checks):
    for path, d in checks:
        ev = d["events"]
        inp = d["input"] if isinstance(d["input"], dict) else {"text": d["input"]}
        calls = [c for e in ev if e.get("type") == "calls" for c in (e.get("data") or e.get("calls") or [])]
        sid = await store.save_check(inp, last(ev, "claim", {}), last(ev, "idealo", {}), last(ev, "specs", []),
                                     last(ev, "clones", {}), last(ev, "life", {}), last(ev, "cost", {}),
                                     d.get("verdict") or {}, calls)
        print(sid, path)


if __name__ == "__main__":
    asyncio.run(save_all(load_checks()))
