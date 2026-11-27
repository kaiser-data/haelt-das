// Opens the side panel next to the shop page and relays the page data and the verdict.
try { chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true }).catch(() => {}); } catch (e) { /* no side panel API (headless) */ }

chrome.runtime.onMessage.addListener((msg, sender) => {
  if (msg?.type === "haeltdas-check" && sender.tab) {
    const tabId = sender.tab.id;
    // open first: the user gesture from the badge click is only valid synchronously
    try { chrome.sidePanel?.open?.({ tabId })?.catch?.(() => {}); } catch (e) { /* needs a real click; the toolbar icon still opens the panel */ }
    chrome.storage.session.set({ pending: { tabId, page: msg.page, at: Date.now() } });
    chrome.runtime.sendMessage({ type: "haeltdas-run", tabId, page: msg.page }).catch(() => {});
  }
  if (msg?.type === "haeltdas-verdict-from-panel" && msg.tabId) {
    chrome.tabs.sendMessage(msg.tabId, { type: "haeltdas-verdict", verdict: msg.verdict, perDay: msg.perDay }).catch(() => {});
  }
});
