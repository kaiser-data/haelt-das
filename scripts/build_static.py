"""Build dist/: the web app as static files that replay the recorded live runs in the browser.

  python3 scripts/build_static.py
Deployed to Cloudflare as static assets (wrangler.jsonc). No server, no API keys, no live calls:
the page answers /api/check and /api/replay itself from dist/recordings/*.json, with the same
matching rules and pacing as app/server.py.
"""
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WEB, SAMPLES, DIST = ROOT / "web", ROOT / "samples" / "batch", ROOT / "dist"

REPLAY_JS = r"""
<script>
// Static build: answer the API from the recorded live runs, in the browser (same rules as app/server.py)
(() => {
  const PACE = {running: 350, step: 700, calls: 250, verdict: 900};
  const tokens = t => new Set((String(t || "").toLowerCase().match(/[a-z0-9äöüß]+/g) || []));
  let index = null;
  const loadIndex = async () => index ??= await (await fetch("/recordings/index.json")).json();
  async function find(text) {
    const want = tokens(text);
    let best = null, bestScore = 0;
    for (const r of await loadIndex()) {
      const have = tokens(r.input);
      if ([...want].some(t => /^\d+$/.test(t) && !have.has(t))) continue;  // a different price or spec is a different listing
      const inter = [...want].filter(t => have.has(t)).length;
      const score = inter / Math.max(new Set([...want, ...have]).size, 1);
      if (score > bestScore) { best = r; bestScore = score; }
    }
    return bestScore >= 0.75 ? best : null;
  }
  const sse = ev => `data: ${JSON.stringify(ev)}\n\n`;
  async function replayResponse(body) {
    const enc = new TextEncoder();
    const stream = new ReadableStream({
      async start(ctl) {
        const send = ev => ctl.enqueue(enc.encode(sse(ev)));
        const text = typeof body?.text === "string" ? body.text.trim() : "";
        const hit = text ? await find(text) : null;
        if (!text) send({type: "error", message: "This online demo replays the example listings (pick one). Links, screenshots and pages need a live check."});
        else if (!hit) send({type: "error", message: "No recorded run for this listing. Pick one of the examples; live checks run on the builder's machine."});
        else {
          const rec = await (await fetch(`/recordings/${hit.file}`)).json();
          send({type: "step", id: "replay", status: "done", title: `Recorded live run (27 Nov 2026), replayed faster: ${String(rec.input).slice(0, 90)}`});
          for (const ev of rec.events) {
            await new Promise(r => setTimeout(r, PACE[ev.status === "running" ? "running" : ev.type] ?? 300));
            send(ev);
          }
        }
        send({type: "end"});
        ctl.close();
      }
    });
    return new Response(stream, {headers: {"Content-Type": "text/event-stream"}});
  }
  const realFetch = window.fetch.bind(window);
  window.fetch = (url, opts) => (typeof url === "string" && url.startsWith("/api/"))
    ? replayResponse(JSON.parse(opts?.body || "{}"))
    : realFetch(url, opts);
})();
</script>
"""


def main():
    shutil.rmtree(DIST, ignore_errors=True)
    (DIST / "recordings").mkdir(parents=True)
    html = (WEB / "index.html").read_text(encoding="utf-8")
    html = html.replace('const REPLAY = new URLSearchParams(location.search).has("replay");', "const REPLAY = true;")
    html = html.replace('const IS_LOCAL = ["127.0.0.1", "localhost"].includes(location.hostname);', "const IS_LOCAL = true;  // the start screen replaces the auto-start")
    html = html.replace("<script>", REPLAY_JS + "<script>", 1)
    (DIST / "index.html").write_text(html, encoding="utf-8")
    for name in ("manifest.webmanifest", "sw.js"):
        shutil.copy(WEB / name, DIST / name)
    shutil.copytree(WEB / "icons", DIST / "icons")
    index = []
    for path in sorted(SAMPLES.glob("*.json")):
        rec = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(rec.get("events"), list):
            continue
        shutil.copy(path, DIST / "recordings" / path.name)
        inp = rec["input"] if isinstance(rec["input"], str) else json.dumps(rec["input"], ensure_ascii=False)
        index.append({"file": path.name, "input": inp})
    (DIST / "recordings" / "index.json").write_text(json.dumps(index, ensure_ascii=False), encoding="utf-8")
    print(f"dist/ built: {len(index)} recordings")


if __name__ == "__main__":
    main()
