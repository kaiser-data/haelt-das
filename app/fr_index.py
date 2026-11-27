"""French durability index (indice de durabilité, loi AGEC): official, filed per model on data.gouv.fr.

Source: data/fr_durabilite_consolidated.csv, built from 205 manufacturer datasets (TVs, washing machines).
Overall score = 0.5 x repairability + 0.5 x reliability (recovered from the data, R^2 0.94-0.998).
"""
import csv
import re
from functools import lru_cache
from pathlib import Path

CSV = Path(__file__).resolve().parent.parent / "data" / "fr_durabilite_consolidated.csv"


def _norm(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


@lru_cache(maxsize=1)
def _rows():
    if not CSV.exists():
        return []
    with CSV.open(encoding="utf-8") as fh:
        return [r for r in csv.DictReader(fh) if r.get("note_id")]


def _f(x):
    try:
        return round(float(str(x).replace(",", ".")), 1)
    except (TypeError, ValueError):
        return None


def lookup(claim):
    """Return the filed index for this model, or None. A model code in the listing (>= 6 chars, letters and digits)
    must equal the filed code or be its prefix (French SKUs carry region suffixes like '.AEU' or 'XXC')."""
    raw = " ".join(str(claim.get(k) or "") for k in ("model", "title", "idealo_exact_query"))
    tokens = {_norm(t) for t in re.split(r"[\s,/()]+", raw)}
    tokens = {t for t in tokens if len(t) >= 6 and re.search(r"\d", t) and re.search(r"[a-z]", t)}
    if not tokens:
        return None
    best = None
    for r in _rows():
        for key in (r.get("nom_modele"), r.get("id_modele")):
            k = _norm(key)
            if len(k) < 6:
                continue
            for t in tokens:
                if k == t or (k.startswith(t) and len(k) - len(t) <= 5):
                    score = len(t) * 10 - (len(k) - len(t))
                    if best is None or score > best[0]:
                        best = (score, r)
    if not best:
        return None
    r = best[1]
    return {"model": r.get("nom_modele") or r.get("id_modele"), "category": r.get("cat"),
            "filed_by": r.get("nom_metteur_sur_le_marche"), "date": r.get("date_calcul"),
            "overall": _f(r.get("note_id")), "repairability": _f(r.get("note_reparabilite")),
            "reliability": _f(r.get("note_fiabilite")),
            "detail_url": r.get("url_tableau_detail_notation") or None,
            "source": "data.gouv.fr · indice de durabilité (self-declared by the manufacturer, checked by DGCCRF)"}
