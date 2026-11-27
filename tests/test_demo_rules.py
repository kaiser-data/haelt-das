"""The demo listings, checked by the deterministic rules alone (no model, no network).

Each test is one listing from the demo. Run: pytest -v
"""
from app import rules


def rule_ids(specs, price, category):
    return [f["rule"] for f in rules.check(specs, price, category)]


def test_21v_drill_is_really_an_18v_pack():
    assert rule_ids({"voltage_v": 21}, 39.99, "cordless drill") == ["voltage_inflation"]


def test_branded_18v_drill_is_left_alone():
    assert rule_ids({"voltage_v": 18}, 89.0, "cordless drill") == []


def test_50000mah_powerbank_at_180g_breaks_physics():
    flags = rules.check({"capacity_mah": 50000, "weight_g": 180}, 29.99, "power bank")
    assert [f["rule"] for f in flags] == ["impossible_capacity"]
    assert flags[0]["severity"] == "high"


def test_real_20000mah_powerbank_passes():
    assert rule_ids({"capacity_mah": 20000, "weight_g": 400}, 39.0, "power bank") == []


def test_2tb_usb_stick_for_15_euro_is_fake_capacity():
    assert rule_ids({"storage_tb": 2}, 15.99, "usb stick") == ["fake_capacity"]


def test_12000_lumen_beamer_under_300_euro_is_inflated():
    assert rule_ids({"lumen": 12000}, 89.0, "projector") == ["lumen_inflation"]


def test_glucose_smartwatch_triggers_fda_warning():
    assert rule_ids({"health_claims": ["Blutzuckermessung ohne Stechen"]}, 49.0, "smartwatch") == ["health_claim"]


def test_empty_specs_produce_no_flags():
    assert rules.check({}, None, "") == []


def test_defect_listing_is_not_a_working_product():
    assert rules.not_working({"title": "Bosch PSR 18 Ersatzteil/Defekt – nicht funktionsfähig"}) == "Defekt"
    assert rules.not_working({"title": "iPhone 12", "condition": "For parts or not working"}) == "For parts"
    assert rules.not_working({"title": "Lave-linge", "condition": "ne fonctionne pas"}) == "ne fonctionne pas"
    assert rules.not_working({"title": "Kopfhörer", "condition": "broken, does not charge"}) == "broken"


def test_model_coded_defective_condition_counts_too():
    assert rules.not_working({"title": "Saugroboter", "condition": "siehe Fotos", "condition_code": "defective"}) == "siehe Fotos"


def test_working_listings_are_not_flagged_as_broken():
    working = ["Ersatzteil Akku für Dyson V8, neu", "Akkuschrauber, kein Defekt, top Zustand", "defektfrei, wie neu",
               "Verpackung defekt, Gerät neu", "nicht für Bastler, voll funktionsfähig", "funktioniert nicht nur mit Android",
               "Adapter, not working with iPhone 15? Ask us", "sans défaut, jamais en panne"]
    for title in working:
        assert rules.not_working({"title": title}) is None, title


def test_wear_counts_must_be_complete_and_positive():
    assert rules.wear_counts({"low": 80, "mid": 20, "high": 40}) == {"low": 20, "mid": 40, "high": 80}
    for bad in ({}, None, {"low": 20, "mid": None, "high": 80}, {"low": "40+", "mid": 50, "high": 60},
                {"low": 0, "mid": 10, "high": 20}, {"low": float("nan"), "mid": 1, "high": 2}):
        assert rules.wear_counts(bad) is None, bad


def test_vague_green_claim_without_certificate_is_unproven():
    out = rules.green_claims(["100% nachhaltig"], [])
    assert out[0]["status"] == "unproven"


def test_green_claim_with_named_certificate_is_backed():
    out = rules.green_claims(["Bio-Baumwolle"], ["GOTS"])
    assert out[0]["status"] == "backed by a named certificate"
