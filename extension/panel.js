// Side panel: hands the product page to the Hält das? app (iframe) and sends the verdict back to the page badge.
const frame = document.getElementById("app");
let ready = false, queued = null, currentTab = null;
frame.addEventListener("load", () => { ready = true; if (queued) send(queued); });

function send(job) {
  currentTab = job.tabId;
  if (!ready) { queued = job; return; }
  queued = null;
  frame.contentWindow.postMessage({ type: "haeltdas-page", page: job.page }, "*");
}

async function grabActive() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  const [{ result }] = await chrome.scripting.executeScript({
    target: { tabId: tab.id },
    func: () => ({ url: location.href, title: document.title, text: document.body.innerText.slice(0, 8000),
                   images: [document.querySelector('meta[property="og:image"]')?.content].filter(Boolean) }),
  });
  send({ tabId: tab.id, page: result });
}
document.getElementById("check").onclick = grabActive;

// a click on the page badge that happened before this panel existed
chrome.storage.session.get("pending").then(({ pending }) => {
  if (pending && Date.now() - pending.at < 15000) { chrome.storage.session.remove("pending"); send(pending); }
});
chrome.runtime.onMessage.addListener(msg => {
  if (msg?.type === "haeltdas-run") { chrome.storage.session.remove("pending"); send(msg); }
});
addEventListener("message", e => {
  if (e.data?.type === "haeltdas-result" && currentTab != null)
    chrome.runtime.sendMessage({ type: "haeltdas-verdict-from-panel", tabId: currentTab, verdict: e.data.verdict, perDay: e.data.perDay });
});
