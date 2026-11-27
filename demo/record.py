"""Record one real take of the app (CDP screencast, 1920x1080, 30 fps) with timestamp marks.

  python3 demo/record.py
Output: demo/clips/demo.mp4 + demo/clips/demo.marks.json
Adapted from the modal-video-production kit (capture/record.py).
"""
import asyncio
import base64
import json
import pathlib
import shutil
import subprocess
import time

from playwright.async_api import async_playwright

BASE = "http://127.0.0.1:8787"
OUT = pathlib.Path(__file__).parent / "clips"
VW, VH = 1920, 1080
CHROME = ("/Users/marty/Library/Caches/ms-playwright/chromium-1255/chrome-mac-arm64/"
          "Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing")
CURSOR_JS = """
document.addEventListener('DOMContentLoaded', () => {
  const c = document.createElement('div');
  c.style.cssText = 'position:fixed;left:0;top:0;width:26px;height:26px;margin:-13px 0 0 -13px;border-radius:50%;'
    + 'background:rgba(17,24,39,.55);border:3px solid #fff;box-shadow:0 2px 10px rgba(0,0,0,.35);'
    + 'z-index:2147483647;pointer-events:none;transition:transform .15s ease;transform:translate(-100px,-100px)';
  document.body.appendChild(c);
  let x = -100, y = -100, s = 1;
  const paint = () => { c.style.transform = `translate(${x}px,${y}px) scale(${s})`; };
  addEventListener('mousemove', e => { x = e.clientX; y = e.clientY; paint(); }, true);
  addEventListener('mousedown', () => { s = 0.7; paint(); }, true);
  addEventListener('mouseup', () => { s = 1; paint(); }, true);
});
"""
MARKS = []


def mark(name):
    MARKS.append((name, time.time()))


async def smooth_scroll(pg, dy, ms):
    steps = max(1, ms // 16)
    for _ in range(steps):
        await pg.mouse.wheel(0, dy / steps)
        await pg.wait_for_timeout(16)


async def glide(pg, x0, y0, x1, y1, ms):
    steps = max(1, ms // 16)
    for i in range(steps + 1):
        t = i / steps
        e = t * t * (3 - 2 * t)
        await pg.mouse.move(x0 + (x1 - x0) * e, y0 + (y1 - y0) * e)
        await pg.wait_for_timeout(16)


async def scroll_to(pg, sel, top=90, ms=1600):
    b = await pg.locator(sel).first.bounding_box()
    await smooth_scroll(pg, b["y"] - top, ms)


async def scene(pg):
    await pg.goto(BASE + "/", wait_until="networkidle")
    mark("start")
    await pg.wait_for_timeout(1500)
    chip = pg.locator(".chip").nth(0)
    b = await chip.bounding_box()
    await glide(pg, 600, 400, b["x"] + b["width"] / 2, b["y"] + b["height"] / 2, 900)
    await pg.wait_for_timeout(300)
    mark("click")
    await chip.click()
    await pg.wait_for_selector(".receipt[style*='block']", timeout=240000)
    mark("receipt")
    await pg.wait_for_timeout(1500)
    await pg.wait_for_selector("#verdict[style*='block']", timeout=240000)
    mark("verdict")
    await pg.wait_for_timeout(2500)
    mark("scroll_receipt")
    await scroll_to(pg, "#receipt", top=60, ms=1800)
    await pg.wait_for_timeout(4500)
    mark("scroll_reasons")
    await scroll_to(pg, "#cards .card", top=60, ms=1800)
    await pg.wait_for_timeout(4500)
    mark("scroll_cards")
    await smooth_scroll(pg, 520, 2600)
    await pg.wait_for_timeout(4000)
    await smooth_scroll(pg, 520, 2600)
    await pg.wait_for_timeout(4000)
    mark("scroll_calls")
    await pg.evaluate("window.scrollTo({top: 0, behavior: 'instant'})")
    await scroll_to(pg, "#calls", top=200, ms=1200)
    await pg.wait_for_timeout(4500)
    mark("end")


async def main():
    name = "demo"
    fdir = OUT / "_frames" / name
    shutil.rmtree(fdir, ignore_errors=True)
    fdir.mkdir(parents=True)
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path=CHROME)
        ctx = await b.new_context(viewport={"width": 1200, "height": 675}, device_scale_factor=1.6)
        await ctx.add_init_script(CURSOR_JS)
        pg = await ctx.new_page()
        cdp = await ctx.new_cdp_session(pg)
        frames = []

        async def on_frame(ev):
            f = fdir / f"{len(frames):06d}.jpg"
            f.write_bytes(base64.b64decode(ev["data"]))
            frames.append((ev["metadata"]["timestamp"], f))
            try:
                await cdp.send("Page.screencastFrameAck", {"sessionId": ev["sessionId"]})
            except Exception:  # noqa: BLE001
                pass

        cdp.on("Page.screencastFrame", lambda ev: asyncio.ensure_future(on_frame(ev)))
        await cdp.send("Page.startScreencast", {"format": "jpeg", "quality": 92, "maxWidth": VW, "maxHeight": VH,
                                                "everyNthFrame": 1})
        await scene(pg)
        await pg.wait_for_timeout(300)
        await cdp.send("Page.stopScreencast")
        await b.close()
    frames.sort()
    lst = fdir / "list.txt"
    with lst.open("w") as fh:
        for (t, f), (t2, _) in zip(frames, frames[1:] + [(frames[-1][0] + 1 / 30, None)]):
            fh.write(f"file '{f.name}'\nduration {max(t2 - t, 1 / 60):.4f}\n")
        fh.write(f"file '{frames[-1][1].name}'\n")
    dst = OUT / f"{name}.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst),
                    "-vf", f"fps=30,scale={VW}:{VH}:flags=lanczos,format=yuv420p",
                    "-c:v", "libx264", "-crf", "18", "-preset", "veryfast", "-g", "15", str(dst)], check=True)
    t0 = frames[0][0]
    (OUT / f"{name}.marks.json").write_text(json.dumps({k: round(t - t0, 2) for k, t in MARKS}, indent=1))
    shutil.rmtree(fdir, ignore_errors=True)
    print(f"recorded {dst} frames={len(frames)} span={frames[-1][0] - t0:.1f}s")


asyncio.run(main())
