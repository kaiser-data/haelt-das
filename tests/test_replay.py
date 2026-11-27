"""Replay of recorded live runs: every example chip must find its recording, nothing else may borrow one.

These would have caught the bug where a chip's text no longer matched its recording ("No recorded run").
"""
import asyncio
import json
import re
from pathlib import Path

from app import server

INDEX = (Path(__file__).resolve().parent.parent / "web" / "index.html").read_text(encoding="utf-8")
CHIPS = [q.replace("&quot;", '"') for q in re.findall(r'class="chip"(?: hidden)? data-q="([^"]+)"', INDEX)]


class _NoWait(dict):
    """Replay pacing of zero, so the tests don't wait for the recordable speed."""
    def get(self, key, default=None):
        return 0


def stream(inp):
    server.REPLAY_PACE = _NoWait()
    async def collect():
        return [json.loads(chunk[5:]) for chunk in [e async for e in server._replay_stream(inp)]]
    return asyncio.run(collect())


def test_page_has_example_chips():
    assert len(CHIPS) >= 8


def test_every_chip_finds_its_recording():
    missing = [q[:50] for q in CHIPS if server._find_recording(q) is None]
    assert missing == []


def test_edited_price_does_not_borrow_a_recording():
    drill = next(q for q in CHIPS if "21V" in q)
    assert server._find_recording(drill.replace("39,99", "399,99")) is None


def test_unknown_listing_gets_no_recording():
    assert server._find_recording("iPhone 17 Pro 256 GB, 1.299 €") is None


def test_replay_names_the_recording_then_ends_with_a_verdict():
    events = stream({"text": next(q for q in CHIPS if "LG OLED" in q)})
    assert events[0]["id"] == "replay" and events[0]["title"].startswith("Recorded live run")
    assert any(e["type"] == "verdict" and e["data"]["verdict"] == "ASK" for e in events)
    assert events[-1] == {"type": "end"}


def test_links_and_screenshots_are_refused_not_run_live():
    for inp in ({"url": "https://example.com/x"}, {"image": "data:image/png;base64,AAAA"}, None, [], {"text": 42}):
        events = stream(inp)
        assert events[0]["type"] == "error" and events[-1] == {"type": "end"}
