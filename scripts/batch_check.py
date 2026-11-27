"""Run a set of test products through the full pipeline, 3 at a time.

  .venv/bin/python scripts/batch_check.py
Writes samples/batch/<slug>.json (events + verdict); app/store.py also saves to Supabase when configured.
"""
import asyncio
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")
from app import pipeline  # noqa: E402

PRODUCTS = [
    "Brushless Akkuschrauber Set 21V, Akku-Bohrschrauber Bürstenlos 2x 2000mAh Akku, 60Nm, 4,7 Sterne (1.832 Bewertungen), 39,99 €, Marke: SEESII",
    "USB Stick 2TB, USB 3.0 Speicherstick 2000GB, Metall, wasserdicht, 4,5 Sterne (920 Bewertungen), 15,99 €, no-name",
    "Powerbank 50000mAh, 22,5W Schnellladung, nur 180g, 4,6 Sterne (2.410 Bewertungen), 24,99 €, no-name",
    "Bosch Akkuschrauber PSR 18 LI-2 (18V, 2x Akku, 2-Gang), 4,7 Sterne, 129 €, Marke Bosch",
    "Samsung Galaxy A56 5G 128GB Smartphone, 5000 mAh, IP67, 6 Jahre Updates, 329 €",
    "Smartwatch mit Blutzuckermessung ohne Stechen, Blutdruck, EKG, 4,4 Sterne (3.100 Bewertungen), 29,99 €, no-name",
    "Mini Beamer 4K 12000 Lumen, WiFi 6, Bluetooth, Heimkino, 4,5 Sterne (5.600 Bewertungen), 89,99 €, no-name",
    "HP DeskJet 2720e Multifunktionsdrucker, Tintenstrahl, WLAN, 49 €",
    "Dyson V8 Cyclone Akku-Staubsauger, 40 Min Laufzeit, 199 €",
    "Saugroboter mit Wischfunktion, App-Steuerung, 3000Pa, 4,5 Sterne (1.200 Bewertungen), 119 €, Marke: ONSON-like no-name",
]


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower())[:50].strip("-")


async def one(text, sem):
    if (ROOT / "samples" / "batch" / f"{slug(text)}.json").exists():
        return  # already checked
    async with sem:
        t = time.time()
        events, verdict = [], None
        try:
            async for ev in pipeline.run({"text": text}):
                events.append(ev)
                if ev["type"] == "verdict":
                    verdict = ev["data"]
        except Exception as e:  # noqa: BLE001 - one bad product must not stop the batch
            events.append({"type": "error", "message": str(e)})
        out = ROOT / "samples" / "batch" / f"{slug(text)}.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({"input": text, "events": events, "verdict": verdict}, ensure_ascii=False,
                                  indent=1, default=str))
        cost = next((e["data"] for e in events if e.get("id") == "cost" and e.get("status") == "done"), {}) or {}
        me = (cost.get("rows") or [{}])[0]
        print(f"{time.time() - t:5.0f}s  {(verdict or {}).get('verdict', 'ERROR'):16} "
              f"€/day {(me.get('per_day') or {}).get('mid')}  {text[:60]}", flush=True)


async def main():
    sem = asyncio.Semaphore(3)
    await asyncio.gather(*[one(p, sem) for p in PRODUCTS])


asyncio.run(main())
