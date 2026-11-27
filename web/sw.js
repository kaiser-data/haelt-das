// Hält das? service worker: caches the app shell so the installed app opens instantly and offline.
// Checks themselves (/api/*) always go to the network: a verdict must never come from a stale cache.
const SHELL = "haeltdas-shell-v1";
const SHELL_FILES = ["/", "/manifest.webmanifest", "/icons/icon-192.png", "/icons/icon-512.png"];

self.addEventListener("install", event => {
  event.waitUntil(caches.open(SHELL).then(cache => cache.addAll(SHELL_FILES)).then(() => self.skipWaiting()));
});

async function dropOldShells() {
  // one at a time: there are only ever a handful of our own old shell versions to delete
  for (const key of await caches.keys()) {
    if (key.startsWith("haeltdas-shell-") && key !== SHELL) await caches.delete(key);
  }
}

self.addEventListener("activate", event => {
  event.waitUntil(dropOldShells().then(() => self.clients.claim()));
});

self.addEventListener("fetch", event => {
  const url = new URL(event.request.url);
  if (event.request.method !== "GET" || url.origin !== location.origin || url.pathname.startsWith("/api/")) return;
  if (event.request.mode === "navigate") {
    // network first, so a new version shows up at once; the cached shell only when offline
    event.respondWith(
      fetch(event.request)
        .then(res => {
          if (res.ok && url.pathname === "/") {  // keep the offline copy as fresh as the last successful visit
            const copy = res.clone();
            event.waitUntil(caches.open(SHELL).then(cache => cache.put("/", copy)));
          }
          return res;
        })
        .catch(() => caches.match("/"))
    );
    return;
  }
  event.respondWith(caches.match(event.request).then(hit => hit || fetch(event.request)));
});
