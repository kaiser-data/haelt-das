"""French durability index lookup: real rows from data/fr_durabilite_consolidated.csv, offline."""
from app import fr_index


def test_lg_tv_gets_its_filed_scores():
    hit = fr_index.lookup({"title": "LG OLED77B65LA 77 Zoll OLED TV"})
    assert hit["model"] == "OLED77B65LA.AEU"
    assert hit["category"] == "téléviseur"
    assert (hit["overall"], hit["repairability"], hit["reliability"]) == (8.0, 8.3, 7.7)


def test_code_without_french_region_suffix_matches_the_same_row():
    bare = fr_index.lookup({"model": "OLED77B65LA"})
    full = fr_index.lookup({"model": "OLED77B65LA.AEU"})
    assert bare is not None and bare == full


def test_brandt_washing_machine():
    hit = fr_index.lookup({"title": "Brandt BAM284QWL"})
    assert hit["model"] == "BAM284QWL"
    assert hit["category"] == "lave-linge"
    assert (hit["overall"], hit["repairability"], hit["reliability"]) == (8.3, 8.8, 7.8)


def test_listing_without_model_code_has_no_match():
    assert fr_index.lookup({"title": "Fernseher 55 Zoll"}) is None


def test_short_or_digits_only_token_has_no_match():
    assert fr_index.lookup({"title": "TV 2026"}) is None


def test_source_always_set_and_detail_url_never_invented():
    for claim in ({"title": "LG OLED77B65LA"}, {"title": "Brandt BAM284QWL"}):
        hit = fr_index.lookup(claim)
        assert hit["source"].startswith("data.gouv.fr")
        assert hit["detail_url"] is None or hit["detail_url"].startswith("https://")
    assert fr_index.lookup({"title": "LG OLED77B65LA"})["detail_url"] is None  # LG filed no detail link
