"""Single source of truth for German federal-state (Bundesland) name
normalisation, shared by keyword_search.py and bertopic_pipeline_v2.py.

Extracted 2026-07-23 so both pipelines resolve raw/abbreviated state labels
(BaWü, MeckPomm, NRW, None/NaN, ...) onto the same 16 canonical names (or
"KMK" for national documents with no Bundesland) instead of maintaining two
parallel implementations that can drift out of sync -- the same
single-source-of-truth pattern already used for stopwords (shared_stopwords.py).
"""
from collections import Counter
from typing import Any
import unicodedata

# Canonical German federal states + best-effort alias resolution. Any raw
# 'state' value not matched here falls through to a Title-Case pass-through
# and is logged for manual review (out/unmapped_states.txt).
CANONICAL_STATES = [
    "Baden-Württemberg", "Bayern", "Berlin", "Brandenburg", "Bremen",
    "Hamburg", "Hessen", "Mecklenburg-Vorpommern", "Niedersachsen",
    "Nordrhein-Westfalen", "Rheinland-Pfalz", "Saarland", "Sachsen",
    "Sachsen-Anhalt", "Schleswig-Holstein", "Thüringen",
]
STATE_ALIASES = {
    "bw": "Baden-Württemberg", "baden wuerttemberg": "Baden-Württemberg",
    "baden-wuerttemberg": "Baden-Württemberg", "bawu": "Baden-Württemberg",
    "by": "Bayern", "bayern": "Bayern",
    "be": "Berlin", "berlin": "Berlin",
    "bb": "Brandenburg", "brandenburg": "Brandenburg",
    "hb": "Bremen", "bremen": "Bremen",
    "hh": "Hamburg", "hamburg": "Hamburg",
    "he": "Hessen", "hessen": "Hessen",
    "mv": "Mecklenburg-Vorpommern", "meckpomm": "Mecklenburg-Vorpommern",
    "mecklenburg vorpommern": "Mecklenburg-Vorpommern",
    "mecklenburg-vorpommern": "Mecklenburg-Vorpommern",
    "ni": "Niedersachsen", "niedersachsen": "Niedersachsen",
    "nrw": "Nordrhein-Westfalen",
    "nordrhein westfalen": "Nordrhein-Westfalen",
    "nordrhein-westfalen": "Nordrhein-Westfalen",
    "rp": "Rheinland-Pfalz", "rlp": "Rheinland-Pfalz",
    "rheinland pfalz": "Rheinland-Pfalz", "rheinland-pfalz": "Rheinland-Pfalz",
    "sl": "Saarland", "saarland": "Saarland",
    "sn": "Sachsen", "sachsen": "Sachsen",
    "st": "Sachsen-Anhalt", "sachsen anhalt": "Sachsen-Anhalt",
    "sachsen-anhalt": "Sachsen-Anhalt",
    "sh": "Schleswig-Holstein", "schleswig holstein": "Schleswig-Holstein",
    "schleswig-holstein": "Schleswig-Holstein",
    "th": "Thüringen", "thueringen": "Thüringen", "thüringen": "Thüringen",
}


def _strip_diacritics(s: str) -> str:
    """Normalise unicode so alias-matching is accent/case insensitive."""
    nfkd = unicodedata.normalize("NFKD", s)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def canonicalize_state(raw: Any, unmapped_tracker: Counter) -> str:
    """Map a raw, messy 'state' string onto one of the 16 canonical German
    federal state names. Unknown values are Title-Cased and tallied in
    `unmapped_tracker` so they can be reviewed/added to STATE_ALIASES later.
    """
    # KMK-issued national documents (Bildungsstandards, EPA, etc.) have no
    # Bundesland by design -- a missing/blank state means "KMK", not "Unbekannt".
    if raw is None or (isinstance(raw, float) and raw != raw):  # NaN check w/o numpy
        return "KMK"
    text = str(raw).strip()
    if not text:
        return "KMK"

    key = _strip_diacritics(text).lower().strip()
    if key in ("<na>", "na", "n/a", "none", "nan"):
        return "KMK"
    if key == "kmk":
        return "KMK"
    if key in STATE_ALIASES:
        return STATE_ALIASES[key]
    # Direct match against canonical list (case-insensitive, accent-insensitive)
    for canon in CANONICAL_STATES:
        if _strip_diacritics(canon).lower() == key:
            return canon

    unmapped_tracker[text] += 1
    return text.title()
