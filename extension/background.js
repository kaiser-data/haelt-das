// Opens the side panel next to the shop page and relays the page data and the verdict.
// Expected failures (no side panel API when headless, no real user gesture, panel not open yet, tab closed)
// are recorded, not swallowed: the last 20 go to chrome.storage.session "diagnostics" ({at, where, error}),
// where the panel and the extension's devtools can read them. One channel, no console noise in shop pages.
const DIAG_MAX = 20;
let diagnosticsDropped = 0;  // entries lost because the store itself failed; reported with the next entry
function recordDiagnostic(where, e) {
  const entry = { at: Date.now(), where, error: String(e?.message || e), dropped_before: diagnosticsDropped };
  chrome.storage.session.get("diagnostics")
    .then(({ diagnostics = [] }) => chrome.storage.session.set({ diagnostics: [...diagnostics, entry].slice(-DIAG_MAX) }))
    .then(() => { diagnosticsDropped = 0; })
    .catch(() => { diagnosticsDropped += 1; });
}
const logSkip = where => e => recordDiagnostic(where, e);

if (chrome.sidePanel?.setPanelBehavior) {
  chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true }).catch(logSkip("setPanelBehavior"));
} else {
  logSkip("setPanelBehavior")("side panel API not available");
}

function openPanel(tabId) {
  // open first: the user gesture from the badge click is only valid synchronously
  try {
    chrome.sidePanel?.open?.({ tabId })?.catch?.(logSkip("sidePanel.open"));
  } catch (e) {
    logSkip("sidePanel.open (needs a real click; the toolbar icon still opens the panel)")(e);
  }
}

chrome.runtime.onMessage.addListener((msg, sender) => {
  if (msg?.type === "haeltdas-check" && sender.tab) {
    const tabId = sender.tab.id;
    openPanel(tabId);
    chrome.storage.session.set({ pending: { tabId, page: msg.page, at: Date.now() } }).catch(logSkip("storage.session"));
    chrome.runtime.sendMessage({ type: "haeltdas-run", tabId, page: msg.page }).catch(logSkip("panel not open yet; it reads 'pending' on load"));
  }
  if (msg?.type === "haeltdas-verdict-from-panel" && msg.tabId) {
    chrome.tabs.sendMessage(msg.tabId, { type: "haeltdas-verdict", verdict: msg.verdict, perDay: msg.perDay })
      .catch(logSkip("tab closed or navigated away"));
  }
});
