"""Cost and evidence hygiene, from the judge-style review on 27 Nov: numbers must not argue against the verdict."""
import asyncio

from app import pipeline, rules


def test_failures_after_weeks_cap_the_whole_life_range():
    life = rules.life_from_failures({"low": 1.5, "mid": 3, "high": 6}, [6, 12])  # reports: 6 and 12 weeks
    assert life["low"] < 0.2 and life["mid"] < 1 and life["high"] <= 3
    assert life["low"] <= life["mid"] <= life["high"]


def test_no_failure_reports_leave_the_estimate_alone():
    assert rules.life_from_failures({"low": 4, "mid": 8, "high": 12}, []) == {"low": 4, "mid": 8, "high": 12}


def test_drill_bits_are_accessories_not_running_costs():
    assert rules.is_accessory("Bohrer-Set 100 Bits") and rules.is_accessory("drill bits")
    assert not rules.is_accessory("Druckerpatrone 302 schwarz") and not rules.is_accessory("HEPA filter")


def test_consumables_cap_is_the_price_except_for_ink_and_capsules():
    assert rules.consumables_cap(40, "cordless drill") == 40
    assert rules.consumables_cap(49, "inkjet printer") == 147


def test_same_model_twice_keeps_the_cheapest_offer():
    alts = [{"name": "Bosch GSR 18V-65", "price": 97.78}, {"name": "Makita DDF482", "price": 168.99},
            {"name": "Bosch GSR 18V-65", "price": 78.99}, {"name": "BOSCH GSR 18V-65 ", "price": 215.99}]
    assert [(a["name"], a["price"]) for a in rules.dedupe_alternatives(alts)] == [("Makita DDF482", 168.99),
                                                                                ("Bosch GSR 18V-65", 78.99)]


def test_youtube_or_unlinked_reason_cannot_be_tier_a():
    assert rules.strict_tier({"tier": "A", "url": "https://www.youtube.com/watch?v=x"})["tier"] == "B"
    assert rules.strict_tier({"tier": "A", "url": None})["tier"] == "B"
    assert rules.strict_tier({"tier": "A", "url": "https://data.economie.gouv.fr/x"})["tier"] == "A"
    assert rules.strict_tier({"tier": "C", "url": "https://reddit.com/r/x"})["tier"] == "C"


def test_running_costs_never_exceed_the_cap(monkeypatch):
    async def fake_chat_json(prompt, **kw):
        return {"items": [{"name": "Saugroboter", "price_eur": 119, "life_years": {"low": 2, "mid": 4, "high": 6}}],
                "consumables": [{"name": "Filter", "idealo_query": "filter", "units_per_year": 50},
                                {"name": "Bürsten-Zubehör Set", "idealo_query": "zubehör", "units_per_year": 10}]}

    async def fake_search(query, country="DE"):
        return {"results": [{"price": "19,99 €", "url": "https://www.idealo.de/x", "name": query}]}

    monkeypatch.setattr(pipeline.llm, "chat_json", fake_chat_json)
    monkeypatch.setattr(pipeline.idealo, "search", fake_search)
    cost = asyncio.run(pipeline.running_cost({"title": "Saugroboter", "category": "robot vacuum", "price_eur": 119},
                                             {"alternatives": []}, {"reports": []}))
    assert [c["name"] for c in cost["consumables"]] == ["Filter"]  # the accessory set is not a running cost
    assert sum(c["per_year"] for c in cost["consumables"]) <= 119
