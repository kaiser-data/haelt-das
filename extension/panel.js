// Reads the product facts from the page the user is looking at (in their own browser, no server-side scraping)
// and hands them to the Hält das? app in the iframe.
function grab() {
  const txt = s => document.querySelector(s)?.innerText?.trim() || null;
  const meta = n => document.querySelector(`meta[property="${n}"],meta[name="${n}"]`)?.content || null;
  const imgs = [meta("og:image"), ...[...document.images].filter(i => i.naturalWidth >= 300).map(i => i.src)]
    .filter(Boolean).slice(0, 4);
  const body = document.body.innerText.replace(/\s+\n/g, "\n").slice(0, 9000);
  return {
    url: location.href,
    title: meta("og:title") || document.title,
    price: txt(".a-price .a-offscreen") || meta("product:price:amount") || null,
    rating: txt("#acrPopover") || null,
    reviews: txt("#acrCustomerReviewText") || null,
    bullets: txt("#feature-bullets") || null,
    images: imgs,
    text: body,
  };
}
document.getElementById("check").onclick = async () => {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  const [{ result }] = await chrome.scripting.executeScript({ target: { tabId: tab.id }, func: grab });
  document.getElementById("app").contentWindow.postMessage({ type: "haeltdas-page", page: result }, "*");
};
