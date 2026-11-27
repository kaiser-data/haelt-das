"""'Receipt from the future': the per-day cost maths, with the Nebius model and idealo replaced by fixed answers."""
import asyncio

from app import pipeline


def run_cost(monkeypatch, claim, plan, life=None, found=None):
    async def fake_chat_json(prompt, **kw):
        return plan

    async def fake_search(query, country="DE"):
        return {"results": []}

    monkeypatch.setattr(pipeline.llm, "chat_json", fake_chat_json)
    monkeypatch.setattr(pipeline.idealo, "search", fake_search)
    return asyncio.run(pipeline.running_cost(claim, found or {"alternatives": []}, life or {"reports": []}))


PLAN = {"items": [{"name": "Akkuschrauber", "price_eur": 73.0, "life_years": {"low": 1, "mid": 2, "high": 4}}]}


def test_price_spread_over_life_gives_cost_per_day(monkeypatch):
    row = run_cost(monkeypatch, {"title": "Akkuschrauber", "category": "cordless drill"}, PLAN)["rows"][0]
    assert row["per_day"]["mid"] == 0.1  # 73 € / (2 years * 365)
    assert row["per_day"]["worst"] > row["per_day"]["mid"] > row["per_day"]["best"]
    assert row["per_year"] == 36.5


def test_failure_reports_pull_the_life_estimate_down(monkeypatch):
    life = {"reports": [{"failure": True, "after_weeks": 13}]}
    row = run_cost(monkeypatch, {"title": "Akkuschrauber", "category": "cordless drill"}, PLAN, life=life)["rows"][0]
    assert row["life_years"]["low"] == 0.25  # broke after 13 weeks
    assert row["per_day"]["worst"] > 0.5


def test_defect_listing_gets_no_per_day_price(monkeypatch):
    claim = {"title": "Akkuschrauber Defekt – nicht funktionsfähig", "category": "cordless drill"}
    row = run_cost(monkeypatch, claim, PLAN)["rows"][0]
    assert row["not_working"] == "defekt"
    assert row["per_day"]["mid"] is None and row["per_year"] is None


def test_alternative_uses_the_idealo_price(monkeypatch):
    plan = {"items": PLAN["items"] + [{"name": "Bosch PSR 18", "price_eur": 1, "life_years": {"low": 4, "mid": 6, "high": 8}}]}
    found = {"alternatives": [{"name": "Bosch PSR 18", "price": 89.0, "url": "https://www.idealo.de/x",
                               "stars": 4.6, "review_count": 900, "offer_count": 40}]}
    rows = run_cost(monkeypatch, {"title": "Akkuschrauber", "category": "cordless drill"}, plan, found=found)["rows"]
    assert rows[1]["price"] == 89.0
    assert rows[1]["per_day"]["mid"] < rows[0]["per_day"]["mid"]  # dearer up front, cheaper per day


def test_tshirt_gets_a_cost_per_wear(monkeypatch):
    plan = {"items": [{"name": "TrendWave Eco T-Shirt", "price_eur": 19.99, "life_years": {"low": 1, "mid": 2, "high": 3}}],
            "wears": {"low": 20, "mid": 40, "high": 80}}
    row = run_cost(monkeypatch, {"title": "TrendWave Eco T-Shirt", "is_clothing": True}, plan)["rows"][0]
    assert row["per_wear"] == {"low": 1.0, "mid": 0.5, "high": 0.25}


def test_non_clothing_never_gets_a_per_wear_line(monkeypatch):
    row = run_cost(monkeypatch, {"title": "Akkuschrauber"}, {**PLAN, "wears": {"low": 1, "mid": 1, "high": 1}})["rows"][0]
    assert "per_wear" not in row
