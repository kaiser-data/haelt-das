"""Deterministic spec-plausibility rules. Physics and market sanity, no model needed."""

LIION_MAX_WH_PER_KG = 270  # best commercial Li-ion cells; packs with housing are lower

# Listings that sell a broken unit or a part: a cost per day of use is meaningless for them.
NOT_WORKING_TERMS = ("defekt", "nicht funktionsfähig", "funktioniert nicht", "für bastler", "bastlerware",
                     "for parts", "not working", "spares or repair", "pour pièces", "hors service", "en panne")


def not_working(claim: dict) -> str | None:
    """Return the matching phrase if the listing says the item is broken or sold as parts, else None."""
    text = " ".join(str(claim.get(k) or "") for k in ("title", "condition")).lower()
    return next((t for t in NOT_WORKING_TERMS if t in text), None)


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
