// Detects product pages, shows a small "Hält das?" badge, and after a check shows the verdict on the page.
(() => {
  if (window.__haeltdas) return; window.__haeltdas = true;

  function jsonLdProduct() {
    for (const s of document.querySelectorAll('script[type="application/ld+json"]')) {
      try {
        const walk = o => {
          if (!o || typeof o !== "object") return null;
          if (Array.isArray(o)) { for (const x of o) { const r = walk(x); if (r) return r; } return null; }
          const t = [].concat(o["@type"] || []).map(String);
          if (t.includes("Product")) return o;
          return walk(o["@graph"]) || null;
        };
        const p = walk(JSON.parse(s.textContent)); if (p) return p;
      } catch (e) { /* malformed JSON-LD on many shops; try the next block */ }
    }
    return null;
  }
  const meta = n => document.querySelector(`meta[property="${n}"],meta[name="${n}"]`)?.content || null;

  function grab() {
    const p = jsonLdProduct() || {};
    const offer = [].concat(p.offers || [])[0] || {};
    const rating = p.aggregateRating || {};
    const txt = s => document.querySelector(s)?.innerText?.trim() || null;
    return {
      url: location.href,
      title: p.name || meta("og:title") || document.title,
      brand: (typeof p.brand === "object" ? p.brand?.name : p.brand) || null,
      gtin: p.gtin13 || p.gtin || p.gtin8 || p.ean || null,
      sku: p.sku || p.mpn || null,
      price: offer.price || offer.lowPrice || meta("product:price:amount") || txt(".a-price .a-offscreen"),
      currency: offer.priceCurrency || null,
      stars: rating.ratingValue || txt("#acrPopover"),
      review_count: rating.reviewCount || rating.ratingCount || txt("#acrCustomerReviewText"),
      description: (p.description || txt("#feature-bullets") || "").slice(0, 2000),
      images: [].concat(p.image || meta("og:image") || []).map(i => (typeof i === "object" ? i.url : i)).filter(Boolean).slice(0, 3),
      text: document.body.innerText.replace(/\s+\n/g, "\n").slice(0, 6000),
    };
  }

  const looksLikeProduct = () => !!jsonLdProduct() || meta("og:type") === "product" || !!document.querySelector("#productTitle");
  if (!looksLikeProduct()) return;

  const host = document.createElement("div");
  host.style.cssText = "position:fixed;right:18px;bottom:18px;z-index:2147483647";
  const root = host.attachShadow({ mode: "open" });
  root.innerHTML = `<style>
    button{all:unset;cursor:pointer;font:700 14px -apple-system,Segoe UI,Helvetica,sans-serif;background:#16130f;color:#f4efe4;
      padding:10px 14px;border-radius:999px;box-shadow:0 4px 14px rgba(0,0,0,.3);display:flex;gap:8px;align-items:center}
    b{color:#ff6b4a} .AVOID{background:#c8361d} .BUY{background:#2f7a3f} .BUY_ALTERNATIVE{background:#1f4f8a} .ASK{background:#b9770e}
    .AVOID b,.BUY b,.BUY_ALTERNATIVE b,.ASK b{color:#fff}
  </style><button id="b"><span>Hält das<b>?</b></span><span id="t">Check</span></button>`;
  document.documentElement.appendChild(host);
  const btn = root.getElementById("b"), label = root.getElementById("t");
  btn.addEventListener("click", () => {
    label.textContent = "checking…";
    let page;
    try { page = grab(); } catch (e) { page = { url: location.href, title: document.title, text: document.body.innerText.slice(0, 6000) }; }
    chrome.runtime.sendMessage({ type: "haeltdas-check", page }).catch(e => { label.textContent = "reload page"; console.warn("Hält das?", e); });
  });
  chrome.runtime.onMessage.addListener(msg => {
    if (msg?.type !== "haeltdas-verdict") return;
    btn.className = msg.verdict || "";
    label.textContent = `${(msg.verdict || "").replace("_", " ")}${msg.perDay != null ? " · €" + Number(msg.perDay).toFixed(2) + "/day" : ""}`;
  });
})();
