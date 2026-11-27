"""Load saved batch results (samples/batch/*.json) into Supabase public.checks."""
import asyncio
import glob
import json

from dotenv import load_dotenv

load_dotenv()
from app import store  # noqa: E402


def last(events, sid, default):
    data = [e.get("data") for e in events if e.get("type") == "step" and e.get("id") == sid and e.get("data") is not None]
    return data[-1] if data else default


async def main():
    for path in sorted(glob.glob("samples/batch/*.json")):
        d = json.load(open(path))
        ev = d["events"]
        inp = d["input"] if isinstance(d["input"], dict) else {"text": d["input"]}
        calls = [c for e in ev if e.get("type") == "calls" for c in (e.get("data") or e.get("calls") or [])]
        sid = await store.save_check(inp, last(ev, "claim", {}), last(ev, "idealo", {}), last(ev, "specs", []),
                                     last(ev, "clones", {}), last(ev, "life", {}), last(ev, "cost", {}),
                                     d.get("verdict") or {}, calls)
        print(sid, path)


asyncio.run(main())
