"""Run one chip through the UI and screenshot the result."""
import sys
from playwright.sync_api import sync_playwright
CHROME = "/Users/marty/Library/Caches/ms-playwright/chromium-1255/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing"
chip = int(sys.argv[1]) if len(sys.argv) > 1 else 0
out = sys.argv[2] if len(sys.argv) > 2 else "demo/shot.png"
with sync_playwright() as p:
    b = p.chromium.launch(executable_path=CHROME)
    pg = b.new_page(viewport={"width": 1440, "height": 1000}, device_scale_factor=1)
    pg.goto("http://127.0.0.1:8787/")
    pg.locator(".chip").nth(chip).click()
    pg.wait_for_selector("#verdict[style*='block']", timeout=240000)
    pg.wait_for_timeout(2500)
    pg.screenshot(path=out, full_page=True)
    b.close()
print("saved", out)
