"""Load the unpacked extension in Chromium, open a product page, check the badge, click it, read what was sent."""
import asyncio, json, sys, tempfile
from playwright.async_api import async_playwright
CHROME = ("/Users/marty/Library/Caches/ms-playwright/chromium-1255/chrome-mac-arm64/"
          "Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing")
EXT = "/Users/marty/claude-projects/hackathons/2026/agentic-commerce/extension"
URL = sys.argv[1]

async def main():
    async with async_playwright() as p:
        ctx = await p.chromium.launch_persistent_context(tempfile.mkdtemp(), executable_path=CHROME, headless=False,
            args=["--headless=new", f"--disable-extensions-except={EXT}", f"--load-extension={EXT}"],
            viewport={"width": 1300, "height": 850})
        sw = ctx.service_workers[0] if ctx.service_workers else await ctx.wait_for_event("serviceworker", timeout=15000)
        print("extension loaded:", sw.url.split("/")[2], "| sidePanel API:", await sw.evaluate("typeof chrome.sidePanel"))
        pg = await ctx.new_page()
        pg.on("console", lambda m: print("page console:", m.text[:200]))
        await pg.goto(URL, wait_until="domcontentloaded", timeout=45000)
        await pg.wait_for_timeout(4000)
        n = await pg.evaluate("document.querySelectorAll('script[type=\"application/ld+json\"]').length")
        badge = await pg.evaluate("[...document.documentElement.children].some(e => e.shadowRoot && e.shadowRoot.getElementById('b'))")
        print("json-ld blocks:", n, "| badge shown:", badge)
        if badge:
            await pg.evaluate("[...document.documentElement.children].find(e => e.shadowRoot && e.shadowRoot.getElementById('b')).shadowRoot.getElementById('b').click()")
            await pg.wait_for_timeout(2500)
            allst = await sw.evaluate("chrome.storage.session.get(null)")
            print("session storage keys:", list(allst.keys()), "| label:", await pg.evaluate("[...document.documentElement.children].find(e => e.shadowRoot && e.shadowRoot.getElementById('b')).shadowRoot.getElementById('t').textContent"))
            pend = allst
            page = (pend.get("pending") or {}).get("page") or {}
            print("sent to panel:", json.dumps({k: page.get(k) for k in ("title","brand","gtin","sku","price","stars","review_count")}, ensure_ascii=False))
            print("images:", page.get("images"))
        await pg.screenshot(path="demo/ext_badge.png")
        await ctx.close()
asyncio.run(main())
