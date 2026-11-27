"""Deterministic spec-plausibility rules. Physics and market sanity, no model needed."""

LIION_MAX_WH_PER_KG = 270  # best commercial Li-ion cells; packs with housing are lower

import math
import re

# Listings that sell a broken unit or a donor for parts: a cost per day of use is meaningless for them.
# Word-boundary patterns (DE/EN/FR); a negation just before the phrase ("kein Defekt", "nicht für Bastler") or a
# packaging noun ("Verpackung defekt") means the item itself works.
_NOT_WORKING = re.compile(
    r"\bdefekte?[rsnm]?\b|\bnicht (?:mehr )?funktionsfähig\b|\bfunktioniert nicht\b(?! nur)|\bohne funktion\b"
    r"|\bfür bastler\b|\bbastlerware\b|\bersatzteilspender\b|\bals ersatzteil\b"
    r"|\bfor parts\b|\bnot working\b(?! with)|\bspares or repairs?\b|\bbroken\b|\bdefective\b|\bfaulty\b"
    r"|\bdoes(?: not|n't) (?:work|turn on|power on|charge)\b"
    r"|\bpour pièces\b|\bhors service\b|\ben panne\b|\bne fonctionne (?:pas|plus)\b|\bdéfectueu(?:x|se)\b")
_NEGATION = {"kein", "keine", "keinen", "keiner", "keinerlei", "nicht", "nie", "ohne", "no", "not", "never", "without",
             "sans", "pas", "aucun", "aucune", "non"}
_PACKAGING = {"verpackung", "ovp", "karton", "box", "packaging", "packung", "emballage", "carton"}


def not_working(claim: dict) -> str | None:
    """The phrase that says this listing sells a broken unit or a donor for parts, as written; else None."""
    for field in ("title", "condition"):
        text = str(claim.get(field) or "")
        for m in _NOT_WORKING.finditer(text.lower()):
            before = re.findall(r"[\wäöüßéèàç]+", text.lower()[:m.start()])[-3:]
            if _NEGATION & set(before) or (before and before[-1] in _PACKAGING):
                continue
            return text[m.start():m.end()]
    if claim.get("condition_code") == "defective":
        return str(claim.get("condition") or "defective")
    return None


def wear_counts(wears) -> dict | None:
    """Validated low/mid/high wear counts (finite, positive, sorted), or None if the estimate is unusable."""
    if not isinstance(wears, dict):
        return None
    try:
        vals = sorted(float(wears[k]) for k in ("low", "mid", "high"))
    except (KeyError, TypeError, ValueError):
        return None
    if not all(math.isfinite(v) and v >= 1 for v in vals):
        return None
    return dict(zip(("low", "mid", "high"), vals))


def check(specs: dict, price_eur, category: str = ""):
    flags = []
    cat = (category or "").lower()
    v = specs.get("voltage_v")
    if v and v in (20, 21) and any(k in cat for k in ("drill", "schrauber", "tool", "werkzeug", "saw", "säge")):
        flags.append({"severity": "warn", "rule": "voltage_inflation",
                      "text": f"\"{v:g}V\" is the unloaded peak voltage of a 5-cell pack; the nominal voltage is 18V. "
                              "Branded tools label the same pack 18V."})
    mah, g = specs.get("capacity_mah"), specs.get("weight_g")
    if mah and g and g > 0:
        wh = mah * 3.7 / 1000
        density = wh / (g / 1000)
        if density > LIION_MAX_WH_PER_KG:
            flags.append({"severity": "high", "rule": "impossible_capacity",
                          "text": f"{mah:,.0f} mAh at {g:g} g would be {density:.0f} Wh/kg; "
                                  f"Li-ion cells top out around {LIION_MAX_WH_PER_KG} Wh/kg. The capacity claim cannot be true."})
    tb = specs.get("storage_tb")
    if tb and price_eur and tb >= 1 and price_eur / tb < 30 and any(k in cat for k in ("usb", "stick", "sd", "flash", "speicher")):
        flags.append({"severity": "high", "rule": "fake_capacity",
                      "text": f"{tb:g} TB for €{price_eur:.0f} is €{price_eur / tb:.0f}/TB. Genuine flash storage of this kind costs "
                              "several times more; this pattern matches fake-capacity drives that report a size they do not have."})
    lm = specs.get("lumen")
    is_projector = any(k in cat for k in ("projector", "beamer"))
    if is_projector and lm and price_eur and lm >= 5000 and price_eur < 300:
        flags.append({"severity": "warn", "rule": "lumen_inflation",
                      "text": f"{lm:,.0f} lumen at €{price_eur:.0f}: budget projectors usually quote non-ANSI 'light source' lumen; "
                              "measured ANSI brightness is typically a fraction of this."})
    for claim in specs.get("health_claims") or []:
        c = claim.lower()
        if any(k in c for k in ("glucose", "blood sugar", "blutzucker", "glycémie")):
            flags.append({"severity": "high", "rule": "health_claim",
                          "text": f"Claims \"{claim}\". The US FDA has warned that smartwatches and rings that claim to measure "
                                  "blood glucose without piercing the skin are not authorised and can be dangerously wrong."})
    return flags


# Generic environmental claims that the EU "Empowering Consumers for the Green Transition" directive treats as
# unfair unless backed by recognised excellent environmental performance or a certification scheme.
VAGUE_GREEN = ("eco", "öko", "nachhaltig", "sustainable", "umweltfreundlich", "environmentally friendly",
               "eco-friendly", "klimaneutral", "climate neutral", "carbon neutral", "co2-neutral", "green",
               "grün", "conscious", "responsible", "verantwortungsvoll", "natürlich", "natural", "planet")


def green_claims(claims, certifications):
    """Vague green claims without a named certification -> 'unproven'."""
    out = []
    certs = [c for c in (certifications or []) if c]
    for c in claims or []:
        low = c.lower()
        vague = any(k in low for k in VAGUE_GREEN)
        out.append({"claim": c, "vague": vague,
                    "status": "backed by a named certificate" if certs else ("unproven" if vague else "specific")})
    return out


# ---- cost and evidence hygiene (deterministic, applied around the model calls) ----

# Categories whose running costs can legitimately exceed the product price every year (ink, capsules).
HIGH_RUNNING_COST = ("printer", "coffee", "espresso", "capsule")
# Accessories a buyer may add, not parts the product needs to keep working.
ACCESSORY_WORDS = re.compile(r"\b(bits?|bohrer|aufs[aä]tze?|zubeh[oö]r|accessor(y|ies)|attachments?|cases?|tasche|koffer)\b",
                             re.IGNORECASE)


def is_accessory(name: str) -> bool:
    """True for add-ons (drill bits, cases) that must not count as running costs."""
    return bool(ACCESSORY_WORDS.search(name or ""))


def consumables_cap(price_eur, category: str = "") -> float:
    """Upper limit for consumables per year: 3x the price for ink/capsule machines, else 1x the price."""
    price = float(price_eur or 0)
    factor = 3 if any(k in (category or "").lower() for k in HIGH_RUNNING_COST) else 1
    return factor * price


def life_from_failures(life_years: dict, failure_weeks: list) -> dict:
    """Reported failures pull the whole life range down: low to the earliest failure, mid to 4x and high to 12x the
    latest reported failure (at least one year), so "6 years" never sits next to "breaks after weeks"."""
    weeks = [float(w) for w in failure_weeks if w]
    if not weeks:
        return dict(life_years)
    out = dict(life_years)
    out["low"] = round(min(float(out.get("low") or 99), min(weeks) / 52), 2)
    out["mid"] = round(min(float(out.get("mid") or 99), max(weeks) / 52 * 4), 2)
    out["high"] = round(min(float(out.get("high") or 99), max(1.0, max(weeks) / 52 * 12)), 2)
    out["mid"] = max(out["mid"], out["low"])
    out["high"] = max(out["high"], out["mid"])
    return out


def dedupe_alternatives(alternatives: list) -> list:
    """One entry per model (name normalised), the cheapest offer, original order kept."""
    best = {}
    for a in alternatives or []:
        key = re.sub(r"[^a-z0-9]", "", str(a.get("name", "")).lower())
        price = a.get("price") if isinstance(a.get("price"), (int, float)) else math.inf
        if key not in best or price < best[key][1]:
            best[key] = (a, price)
    keep = {id(v[0]) for v in best.values()}
    return [a for a in alternatives or [] if id(a) in keep]


# Videos, marketplaces and forums are user-made: useful, but anyone can write them. At most tier B.
USER_MADE_HOSTS = re.compile(r"(^|\.)(youtube\.com|youtu\.be|alibaba\.com|aliexpress\.com|amazon\.[a-z.]+|temu\.com|"
                             r"ebay\.[a-z.]+|reddit\.com|facebook\.com|tiktok\.com|instagram\.com|trustpilot\.com)$")


def strict_tier(reason: dict) -> dict:
    """Tier A is reserved for evidence that is hard to fake; a tier-A reason from a user-made source becomes B."""
    if not isinstance(reason, dict) or reason.get("tier") != "A":
        return reason
    host = re.sub(r"^https?://", "", str(reason.get("url") or "")).split("/")[0].split(":")[0].lower()
    if not host or USER_MADE_HOSTS.search(host):
        return {**reason, "tier": "B", "tier_note": "user-made or unlinked source: at most tier B"}
    return reason
