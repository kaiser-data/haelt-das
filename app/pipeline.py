"""The 'Hält das?' pipeline: claim -> idealo -> spec check -> clone family -> lifetime -> running cost -> verdict.

`run()` is an async generator of UI events. Each Nebius call is recorded via app.llm.call_log.
"""
import asyncio
import base64
import io
import json
import logging
import math

from app import fr_index, idealo, llm, rules, store, web

log = logging.getLogger(__name__)

ELECTRICITY_EUR_PER_KWH = 0.37  # assumption, shown in the UI and adjustable
# Only these product types have running consumables worth pricing; for tools, bits and chargers are not running costs.
CONSUMABLE_CATEGORIES = ("printer", "coffee", "espresso", "capsule", "toothbrush", "shaver", "razor", "vacuum",
                         "water filter", "air purifier", "humidifier", "lawn", "trimmer", "3d printer")

CLAIM_SCHEMA = """{
 "title": str, "brand": str|null, "model": str|null,
 "category": str (short English, e.g. "cordless drill", "usb stick", "projector", "power bank", "printer", "smartwatch"),
 "price_eur": number|null, "condition": str|null (item condition exactly as written in the listing, e.g. "neu", "gebraucht", "defekt - nicht funktionsfähig"),
 "condition_code": "new"|"used"|"refurbished"|"defective"|null ("defective" only if the listing says the item itself is broken or sold for parts), "stars": number|null, "review_count": int|null,
 "claimed_specs": {"voltage_v": number|null, "capacity_mah": number|null, "weight_g": number|null,
                   "storage_tb": number|null, "lumen": number|null, "health_claims": [str], "other": [str]},
 "idealo_exact_query": str (brand + model for an exact catalogue search),
 "idealo_generic_query": str (German product type + key spec, for finding branded equivalents, e.g. "Akku-Bohrschrauber 18V"),
 "clone_image_query": str (English, generic description used to find look-alike listings under other brand names),
 "failure_queries": {"de": str, "en": str, "fr": str} (searches for reports of this product type/brand breaking),
 "is_clothing": bool (clothing, shoes, home textiles),
 "material": str|null,
 "sustainability_claims": [str] (every environmental/social claim as written, e.g. "nachhaltig", "klimaneutral", "fair produziert"),
 "certifications": [str] (only certificates named in the listing, e.g. "GOTS", "OEKO-TEX STANDARD 100 21.HDE.12345", "Fair Wear")
}"""


def _event(kind, **kw):
    return {"type": kind, **kw}


async def understand(inp):
    """Turn a URL, screenshot, text or extension payload into a ProductClaim."""
    system = "You extract shopping facts. Reply with JSON only. Never invent numbers that are not in the input; use null."
    if inp.get("image"):
        claim = await llm.chat_json(
            f"This is a screenshot of a product listing. Extract:\n{CLAIM_SCHEMA}",
            system=system, model=llm.MODEL_VISION, purpose="read screenshot (vision)", images=[inp["image"]])
        claim["image_url"] = inp["image"]
        return claim
    page = None
    if inp.get("page"):  # from the browser extension
        diag = {k: inp["page"][k] for k in ("jsonld_skipped", "grab_error") if inp["page"].get(k)}
        if diag:  # extension diagnostics belong in the server log, not in the model prompt
            log.info("extension diagnostics for %s: %s", inp["page"].get("url"), diag)
        page = {k: v for k, v in inp["page"].items() if k not in ("jsonld_skipped", "grab_error")}
        text = json.dumps(page, ensure_ascii=False)[:12000]
        img = (page.get("images") or [None])[0]
    elif inp.get("url"):
        try:
            ex = await web.extract(inp["url"])
        except Exception:  # noqa: BLE001 - blocked shops are common; we fall back to the URL text
            ex = None
        text = (ex or {}).get("raw_content", "")[:12000] or inp["url"]
        imgs = (ex or {}).get("images") or []
        img = next((i for i in imgs if isinstance(i, str) and i.startswith("http")), None)
        text = f"URL: {inp['url']}\n\n{text}"
    else:
        text, img = inp.get("text", ""), None
    claim = await llm.chat_json(f"Product listing content:\n{text}\n\nExtract:\n{CLAIM_SCHEMA}",
                                system=system, purpose="read listing")
    claim["image_url"] = img
    claim["source_url"] = inp.get("url") or (page or {}).get("url")
    if page and page.get("gtin"):
        claim["gtin"] = str(page["gtin"])
    return claim


async def find_on_idealo(claim):
    out = {"exact": None, "alternatives": []}
    res, by_gtin = [], False
    if claim.get("gtin"):  # barcode from the shop page's structured data: an exact match, not a fuzzy one
        res = (await idealo.search(claim["gtin"])).get("results") or []
        by_gtin = bool(res)
    if not res:
        res = (await idealo.search(claim.get("idealo_exact_query") or claim["title"])).get("results") or []
    brand = (claim.get("brand") or "").lower()
    for r in res[:5]:
        if by_gtin or (brand and brand in r["name"].lower()):
            d = await idealo.details(r["productRef"])
            offers = d.get("offers") or []
            out["exact"] = {
                "name": r["name"], "url": r["url"], "price": idealo.euro(r.get("price")),
                "offer_count": r.get("totalOfferCount"), "reviews": r.get("userReviewsSummary"),
                "tests": (d.get("testReports") or {}).get("list") or [],
                "overview": d.get("productOverview"),
                "shops": [{"name": o["shop"]["name"], "rating": o["shop"].get("rating"),
                           "marketplace": o["shop"].get("isMarketplace")} for o in offers[:5]],
            }
            break
    generic = claim.get("idealo_generic_query") or claim["category"]
    v = (claim.get("claimed_specs") or {}).get("voltage_v")
    if v in (20, 21):  # search the honest nominal voltage so we compare with branded 18V tools
        generic = generic.replace(f"{v:g}V", "18V").replace(f"{v:g} V", "18V")
    gen = (await idealo.search(generic)).get("results") or []
    for r in gen:
        rv = r.get("userReviewsSummary") or {}
        out["alternatives"].append({
            "name": r["name"], "url": r["url"], "image": r.get("imageUrl"), "price": idealo.euro(r.get("price")),
            "offer_count": r.get("totalOfferCount") or 0, "stars": rv.get("averageRating"),
            "review_count": rv.get("totalReviewCount") or 0, "ref": r["productRef"],
        })
    # established = many shops and many reviews; the scorecard compares against these
    out["alternatives"] = [a for a in out["alternatives"] if (a["offer_count"] or 0) >= 3 and (a["review_count"] or 0) >= 5]
    seen, uniq = set(), []
    for a in out["alternatives"]:
        if a["name"] not in seen:
            seen.add(a["name"])
            uniq.append(a)
    out["alternatives"] = uniq
    out["alternatives"].sort(key=lambda a: (a["offer_count"] or 0) * math.log1p(a["review_count"] or 0), reverse=True)
    out["alternatives"] = out["alternatives"][:4]
    return out


async def _hash_from(src):
    if not src:
        return None
    if src.startswith("data:"):
        try:
            import imagehash
            from PIL import Image
            raw = base64.b64decode(src.split(",", 1)[1])
            return imagehash.phash(Image.open(io.BytesIO(raw)).convert("RGB"))
        except Exception:  # noqa: BLE001
            return None
    return await web.image_hash(src)


async def clone_family(claim):
    """Find look-alike listings under other names, then let a vision model judge 'same physical product?'."""
    q = claim.get("clone_image_query") or claim["title"]
    res = await web.search(q, max_results=8, images=True)
    cands = []
    for im in res.get("images", [])[:10]:
        url = im["url"] if isinstance(im, dict) else im
        cands.append({"image": url, "desc": (im.get("description") if isinstance(im, dict) else "") or "", "source": None})
    for r in res.get("results", [])[:8]:
        cands.append({"image": None, "desc": r.get("title", ""), "source": r.get("url")})
    base_hash = await _hash_from(claim.get("image_url"))
    imgs = [c for c in cands if c["image"]]
    hashes = await asyncio.gather(*[web.image_hash(c["image"]) for c in imgs])
    for c, h in zip(imgs, hashes):
        c["distance"] = int(base_hash - h) if (base_hash is not None and h is not None) else None
    imgs = [c for c in imgs if c.get("distance") is not None or base_hash is None]
    imgs.sort(key=lambda c: c["distance"] if c.get("distance") is not None else 99)
    family = []
    if claim.get("image_url"):
        async def judge(c):
            try:
                v = await llm.chat_json(
                    "Image 1 is the product the user wants to buy. Image 2 is another listing. "
                    "Are they the SAME physical product sold under a different name (same housing shape, button layout, "
                    "battery mount, vents, colour pattern)? Ignore logos and background. Reply JSON: "
                    '{"same": "yes"|"no"|"unsure", "shared_features": [str], "brand_on_image_2": str|null}',
                    model=llm.MODEL_VISION, purpose="clone check (vision)", images=[claim["image_url"], c["image"]],
                    max_tokens=400)
            except Exception:  # noqa: BLE001 - an unreadable candidate image is skipped, not fatal
                return None
            return {**c, **v}
        judged = await asyncio.gather(*[judge(c) for c in imgs[:4]])
        family = [j for j in judged if j and j.get("same") in ("yes", "unsure")]
    names = await llm.chat_json(
        "These are search results for look-alikes of the product below. List distinct BRAND names that appear to sell "
        "the same generic product (rebrands). Reply JSON {\"brands\": [str], \"evidence\": [{\"brand\": str, \"url\": str}]}.\n"
        f"Product: {claim['title']} (brand {claim.get('brand')})\nResults: "
        + json.dumps([{"t": c["desc"], "u": c["source"]} for c in cands if c["desc"]], ensure_ascii=False)[:6000],
        purpose="rebrand names")
    return {"visual_matches": family, "brands": names.get("brands", []), "evidence": names.get("evidence", [])}


async def lifetime_evidence(claim, found):
    fq = claim.get("failure_queries") or {}
    jobs = [web.search(q, max_results=5) for q in fq.values() if q]
    if any(k in (claim.get("category") or "").lower() for k in ("phone", "smartphone", "handy", "tablet")):
        # GSMArena: specs (battery, IP rating) and long-running user opinions for phones
        jobs.append(web.search(f"{claim.get('brand') or ''} {claim.get('model') or claim['title']} battery problems opinions",
                               max_results=5, include_domains=["gsmarena.com"]))
    searches = await asyncio.gather(*jobs, return_exceptions=True)
    snippets = []
    for s in searches:
        if isinstance(s, Exception):
            continue
        for r in s.get("results", []):
            snippets.append({"title": r.get("title"), "url": r.get("url"), "text": (r.get("content") or "")[:500]})
    if not snippets:
        return {"reports": [], "clusters": 0}
    cls = await llm.chat_json(
        "Classify each web snippet. relevant=true ONLY if it is a first-hand or reported case of THIS brand/model (or its "
        "rebrands) failing or holding up. Generic how-to guides, repair tutorials and articles about the product type "
        "in general are relevant=false. Reply JSON "
        '{"items": [{"i": int, "relevant": bool, "failure": bool, "after_weeks": number|null, "component": str|null, '
        '"usage": "hobby"|"heavy"|"pro"|"unknown", "lang": str, "summary_en": str}]}\n'
        f"Product: {claim['title']} ({claim.get('category')})\nSnippets: "
        + json.dumps([{"i": i, **s} for i, s in enumerate(snippets)], ensure_ascii=False)[:9000],
        purpose="classify failure reports", max_tokens=3000)
    reports = []
    for it in cls.get("items", []):
        i = it.get("i")
        if isinstance(i, int) and i < len(snippets) and it.get("relevant"):
            reports.append({**snippets[i], **it})
    clusters = 0
    texts = [r["summary_en"] for r in reports if r.get("summary_en")]
    if len(texts) >= 2:  # cross-language de-duplication: the same story reported in DE and EN counts once
        vecs = await llm.embed(texts, purpose="dedupe reports across languages")
        seen = []
        for v in vecs:
            if not any(_cos(v, s) > 0.85 for s in seen):
                seen.append(v)
        clusters = len(seen)
    tests = ((found or {}).get("exact") or {}).get("tests") or []
    return {"reports": reports, "clusters": clusters, "tests": tests}


def _cos(a, b):
    return sum(x * y for x, y in zip(a, b)) / math.sqrt(sum(x * x for x in a) * sum(y * y for y in b))


async def running_cost(claim, found, life):
    alts = found.get("alternatives", [])
    plan = await llm.chat_json(
        "Estimate ownership cost inputs. Use the evidence; where you must assume, say so in 'basis'.\n"
        "Life: base it on evidence. Failure reports with after_weeks must pull 'low' down to that range; throwaway rebrand "
        "products without tests or spare parts get short lives; established brands with many shops and reviews get longer ones.\n"
        "Consumables: ONLY parts the product needs to keep working and that wear out by design (ink, capsules, filters, "
        "brush heads, blades). Not accessories, not optional bits. Many products have none: return []. "
        "Wears: for clothing, shoes and home textiles estimate how many times the item will be worn/used before it is worn out (use material and failure reports); for everything else return null. Reply JSON:\n"
        '{"items": [{"name": str, "price_eur": number, "life_years": {"low": number, "mid": number, "high": number}, '
        '"basis": str}], "consumables": [{"name": str, "idealo_query": str, "units_per_year": number}], '
        '"energy_kwh_per_year": number|null, "usage_assumption": str, "decisive_question": str, '
        '"wears": {"low": number, "mid": number, "high": number}|null}\n'
        "items[0] must be the product the user looks at; then each alternative in order.\n"
        f"Product: {json.dumps({k: claim.get(k) for k in ('title', 'brand', 'category', 'price_eur', 'stars', 'review_count', 'is_clothing', 'material')}, ensure_ascii=False)}\n"
        f"Alternatives: {json.dumps([{k: a[k] for k in ('name', 'price', 'stars', 'review_count', 'offer_count')} for a in alts], ensure_ascii=False)}\n"
        f"Failure reports: {json.dumps([{k: r.get(k) for k in ('after_weeks', 'component', 'usage')} for r in life.get('reports', []) if r.get('failure')], ensure_ascii=False)}",
        purpose="lifetime + consumables estimate", max_tokens=2500)
    cons_total = 0.0
    consumables = []
    has_consumables = any(k in (claim.get("category") or "").lower() for k in CONSUMABLE_CATEGORIES)
    for c in (plan.get("consumables", [])[:3] if has_consumables else []):
        res = (await idealo.search(c["idealo_query"])).get("results") or []
        price = idealo.euro(res[0].get("price")) if res else None
        if price:
            per_year = min(price * float(c.get("units_per_year") or 0), 3 * (claim.get("price_eur") or price))
            cons_total += per_year
            consumables.append({**c, "price_eur": price, "per_year": round(per_year, 2), "url": res[0]["url"],
                                "found": res[0]["name"]})
    energy = (plan.get("energy_kwh_per_year") or 0) * ELECTRICITY_EUR_PER_KWH
    rows = []
    for idx, it in enumerate(plan.get("items", [])):
        price = it.get("price_eur") or 0
        if idx > 0 and idx - 1 < len(alts) and alts[idx - 1].get("price"):
            price = alts[idx - 1]["price"]
        life_y = dict(it.get("life_years") or {})
        if idx == 0:  # evidence beats optimism: reported failures cap the low end of the life estimate
            weeks = [r["after_weeks"] for r in life.get("reports", []) if r.get("failure") and r.get("after_weeks")]
            if weeks:
                life_y["low"] = round(min(float(life_y.get("low") or 99), min(weeks) / 52), 2)
                life_y["mid"] = round(min(float(life_y.get("mid") or 99), max(weeks) / 52 * 4), 2)
        per_year_running = cons_total + energy  # same consumable class assumed across alternatives

        def per_day(years):
            years = max(float(years or 0.1), 0.05)
            return (price + per_year_running * years) / (years * 365)

        rows.append({"name": it["name"], "price": price, "life_years": life_y, "basis": it.get("basis"),
                     "per_day": {"best": round(per_day(life_y.get("high")), 3), "mid": round(per_day(life_y.get("mid")), 3),
                                 "worst": round(per_day(life_y.get("low")), 3)},
                     "url": alts[idx - 1]["url"] if idx > 0 and idx - 1 < len(alts) else claim.get("source_url")})
    broken = rules.not_working(claim)
    if rows and broken:  # a broken unit has no days of use to spread the price over, and nothing to run
        rows[0].update(not_working=broken, life_years={"low": None, "mid": None, "high": None},
                       per_day={"best": None, "mid": None, "worst": None})
        consumables, energy = [], 0.0
    for r in rows:
        mid = r["per_day"]["mid"]
        r["per_month"], r["per_year"] = (None, None) if mid is None else (round(mid * 30.4, 2), round(mid * 365, 2))
    wears = rules.wear_counts(plan.get("wears"))
    if claim.get("is_clothing") and wears and rows and not broken:
        p = rows[0]["price"] or 0
        rows[0]["per_wear"] = {k: round(p / wears[k], 2) for k in ("low", "mid", "high")}
        rows[0]["wears"] = wears
    return {"rows": rows, "consumables": consumables, "energy_eur_year": round(energy, 2),
            "electricity_price": ELECTRICITY_EUR_PER_KWH, "usage_assumption": plan.get("usage_assumption"),
            "decisive_question": plan.get("decisive_question")}


CERT_DOMAINS = {"oeko-tex": ["oeko-tex.com"], "gots": ["global-standard.org"], "fair wear": ["fairwear.org"],
                "fairtrade": ["fairtrade.net", "fairtrade-deutschland.de"], "grüner knopf": ["gruener-knopf.de"],
                "bluesign": ["bluesign.com"]}


async def responsibility(claim):
    """Green claims, certificate cross-check against official registries, and red flags ONLY from official lists."""
    brand = claim.get("brand") or ""
    claims = rules.green_claims(claim.get("sustainability_claims"), claim.get("certifications"))
    jobs, labels = [], []
    for cert in claim.get("certifications") or []:
        key = next((k for k in CERT_DOMAINS if k in cert.lower()), None)
        if key and brand:
            jobs.append(web.search(f"{brand} {cert}", max_results=3, include_domains=CERT_DOMAINS[key]))
            labels.append(("cert", cert))
    if brand and brand.lower() not in ("generic", "no-name", "none"):
        jobs.append(web.search(f"{brand} textile chemical recall", max_results=3, include_domains=["ec.europa.eu"]))
        labels.append(("flag", "EU Safety Gate"))
        jobs.append(web.search(f"{brand} UFLPA entity list forced labor", max_results=3, include_domains=["dhs.gov", "cbp.gov"]))
        labels.append(("flag", "US forced-labour lists (UFLPA/CBP)"))
    res = await asyncio.gather(*jobs, return_exceptions=True)
    snippets = []
    for (kind, label), r in zip(labels, res):
        if isinstance(r, Exception):
            continue
        for x in r.get("results", []):
            snippets.append({"kind": kind, "label": label, "url": x.get("url"), "text": (x.get("content") or "")[:400]})
    judged = {"certs": [], "flags": []}
    if snippets:
        judged = await llm.chat_json(
            "Official-source check. For each snippet decide strictly: a certificate is confirmed only if the snippet "
            "names this brand as certified/member; a red flag only if the snippet explicitly names this brand in a recall, "
            "ban or entity list. Mentions of other companies or general topics do not count. Reply JSON "
            '{"certs": [{"certificate": str, "confirmed": bool, "url": str}], '
            '"flags": [{"source": str, "listed": bool, "what": str, "url": str}]}\n'
            f"Brand: {brand}\nSnippets: " + json.dumps(snippets, ensure_ascii=False)[:7000],
            purpose="certificate + official red-flag check")
    judged["flags"] = [f for f in judged.get("flags", []) if f.get("listed")]
    merged = {}  # one row per certificate; confirmed wins if any snippet confirms it
    for c in judged.get("certs", []):
        k = (c.get("certificate") or "").strip().lower()
        if k and (k not in merged or (c.get("confirmed") and not merged[k].get("confirmed"))):
            merged[k] = c
    judged["certs"] = list(merged.values())
    return {"claims": claims, **judged}


VERDICT_SYSTEM = """You are a seasoned, fair product buyer. You decide whether a person should buy a product.
Rules: weigh hard-to-fake evidence (independent tests, many established shops, spare parts, official data, physics checks)
above cheap signals (star average, review count, marketing). Country of origin is NOT a signal; throwaway brands and rebrand
cycles are. Statements about environmental harm or worker rights may ONLY repeat an official listing or a named source
from the evidence ("listed on X"); never accuse on your own. Vague green claims without a certificate are "unproven".
For clothing, judge cost per wear. A French durability index (official, per model, 0-10) is tier A evidence. If evidence is thin or contradictory, choose ASK and name the single missing fact that would decide it.
Reply JSON only:
{"verdict": "BUY"|"AVOID"|"BUY_ALTERNATIVE"|"ASK", "headline": str (max 12 words),
 "confidence": "low"|"medium"|"high",
 "reasons": [{"text": str, "tier": "A"|"B"|"C", "url": str|null}],
 "better_alternative": str|null, "missing_fact": str|null, "trust_adjusted_stars": number|null}"""


async def verdict(evidence):
    return await llm.decide("Evidence:\n" + json.dumps(evidence, ensure_ascii=False, default=str)[:24000], system=VERDICT_SYSTEM)


async def run(inp):
    log = []
    llm.call_log.set(log)
    sent = 0

    def calls():
        nonlocal sent
        new = log[sent:]
        sent = len(log)
        return _event("calls", calls=new) if new else None

    yield _event("step", id="claim", status="running", title="Reading the listing")
    claim = await understand(inp)
    public_claim = {k: v for k, v in claim.items() if not (k == "image_url" and str(v).startswith("data:"))}
    yield _event("step", id="claim", status="done", title="Listing read", data=public_claim)
    if (c := calls()):
        yield c

    yield _event("step", id="idealo", status="running", title="Looking it up on idealo")
    found = await find_on_idealo(claim)
    yield _event("step", id="idealo", status="done" if found["exact"] else "warn",
                 title="Found on idealo" if found["exact"] else "Not sold by any idealo shop", data=found)

    fr = fr_index.lookup(claim)
    if fr:
        yield _event("step", id="fr", status="done",
                     title=f"French durability index {fr['overall']}/10 (repair {fr['repairability']}, reliability {fr['reliability']})",
                     data=fr)

    broken = rules.not_working(claim)
    if broken:
        yield _event("step", id="condition", status="warn", title="Sold as broken or for parts: no cost per day",
                     data={"phrase": broken, "text": f"The listing says \"{broken}\": this is a broken unit or a donor for "
                                                       "parts, not a working product. There is no cost per day of use to compare."})
    flags = rules.check(claim.get("claimed_specs") or {}, claim.get("price_eur"), claim.get("category", ""))
    yield _event("step", id="specs", status="warn" if flags else "done",
                 title=f"{len(flags)} spec claim(s) don't add up" if flags else "Specs plausible", data=flags)

    yield _event("step", id="clones", status="running", title="Searching for the same product under other names")
    yield _event("step", id="life", status="running", title="Collecting failure reports (DE/EN/FR)")
    clones_t = asyncio.create_task(clone_family(claim))
    life_t = asyncio.create_task(lifetime_evidence(claim, found))
    tasks = [clones_t, life_t]
    resp_t = None
    if claim.get("is_clothing") or claim.get("sustainability_claims") or claim.get("certifications"):
        yield _event("step", id="resp", status="running", title="Checking green claims and certificates")
        resp_t = asyncio.create_task(responsibility(claim))
        tasks.append(resp_t)
    for fut in asyncio.as_completed(tasks):
        try:
            await fut
        except Exception:  # noqa: BLE001 - one failed evidence branch must not kill the verdict
            pass
        if (c := calls()):
            yield c
    try:
        clones = clones_t.result()
    except Exception as e:  # noqa: BLE001
        clones = {"error": str(e), "visual_matches": [], "brands": []}
    try:
        life = life_t.result()
    except Exception as e:  # noqa: BLE001
        life = {"error": str(e), "reports": []}
    resp = None
    if resp_t:
        try:
            resp = resp_t.result()
        except Exception as e:  # noqa: BLE001
            resp = {"error": str(e), "claims": [], "certs": [], "flags": []}
        unproven = [c for c in resp.get("claims", []) if c["status"] == "unproven"]
        yield _event("step", id="resp", status="warn" if (unproven or resp.get("flags")) else "done",
                     title=f"{len(unproven)} unproven green claim(s), {len([c for c in resp.get('certs', []) if c.get('confirmed')])} "
                           f"certificate(s) confirmed, {len(resp.get('flags', []))} official red flag(s)", data=resp)
    n_brands = len(clones.get("brands") or [])
    yield _event("step", id="clones", status="warn" if (clones.get("visual_matches") or n_brands > 1) else "done",
                 title=f"Look-alikes: {len(clones.get('visual_matches', []))} visual match(es), {n_brands} brand name(s)",
                 data=clones)
    fails = [r for r in life.get("reports", []) if r.get("failure")]
    yield _event("step", id="life", status="warn" if fails else "done",
                 title=f"{len(fails)} failure report(s), {life.get('clusters', 0)} distinct stories", data=life)

    yield _event("step", id="cost", status="running", title="Working out the cost per day")
    cost = await running_cost(claim, found, life)
    yield _event("step", id="cost", status="done", title="Cost per day", data=cost)
    if (c := calls()):
        yield c

    yield _event("step", id="verdict", status="running", title="Deciding (live Nebius call)")
    v = await verdict({"claim": public_claim, "sold_as_broken": broken, "idealo": found, "spec_flags": flags, "clone_family": clones,
                       "french_durability_index": fr, "responsibility": resp, "lifetime": {"reports": [{k: r.get(k) for k in ("url", "failure", "after_weeks", "component", "usage", "summary_en")}
                                                for r in life.get("reports", [])], "tests": life.get("tests")},
                       "cost": cost})
    if (c := calls()):
        yield c
    yield _event("step", id="verdict", status="done", title="Decided (live Nebius call)")
    yield _event("verdict", data=v)
    saved = await store.save_check(inp, public_claim, found, flags, clones, life, cost, v, log)
    if saved:
        yield _event("saved", id=saved)
