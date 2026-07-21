"""Shared German stopword resources for the BERTopic and LDA pipelines.

Single source of truth so both topic-modeling methods filter identical
vocabulary. Before this module existed, BERTopic used NLTK's German list
+ 15 ad-hoc extras and LDA used spaCy's German list + a different 26
ad-hoc extras, with near-zero overlap between the two extras sets --
meaning the two methods reported systematically different top terms for
the same underlying documents. See METHODOLOGY.md sections 1-2 for the
audit and evidence behind every entry below.
"""

from __future__ import annotations

from pathlib import Path

from spacy.lang.de.stop_words import STOP_WORDS as _SPACY_DE_STOP_WORDS

ROOT = Path(__file__).parent
KEYWORDS_PATH = ROOT / "keyword_search" / "in" / "keywords.txt"

# Tier 1 -- curriculum-administrative/pedagogical boilerplate, approved
# 2026-07-21 (METHODOLOGY.md SS2). Not conceptual content -- safe to strip
# for every concept. Derived from a corpus-wide term-frequency audit
# (e.g. the "Kompetenz" word family alone totals 10,467 occurrences and
# was filtered by neither pipeline previously) plus items already in use
# by one pipeline or the other before unification.
ADMIN_STOPWORDS_DE: frozenset[str] = frozenset({
    "schülerinnen", "schüler", "schülerin", "schule",
    "kompetenz", "kompetenzen", "kompetenzerwartungen",
    "sachkompetenz", "urteilskompetenz", "methodenkompetenz", "handlungskompetenz",
    "unterricht", "fach", "themen", "hinweise", "bildung",
    "grundlage", "grundlagen", "aspekte", "bezüge", "lernenden",
    # Bildungsstandards competency-verbs ("Operatoren") -- generic
    # assessment-instruction verbs appearing in nearly every curriculum
    # statement regardless of topic.
    "erläutern", "beschreiben", "beurteilen", "reflektieren", "analysieren",
    "erklären", "bewerten", "erkennen", "diskutieren", "vergleichen",
    "unterscheiden", "darstellen", "kennen",
    # Carried over from LDA's prior exclude_list.txt (now unified here).
    "std", "ustd", "stunde", "bzw", "btv", "ggf", "halbjahr", "oberstufe",
    "einführungsphase", "qualifikationsphase", "hauptphase", "sek",
    "ministerium", "thüringer", "herausgeber", "kapitel", "anderer",
    "hinweis", "besonderer", "jeweilig", "anhand", "folgend", "ständig",
    "vorschlag",
})

# Legacy OCR/extraction-artifact stopwords, mostly carried over from
# BERTopic's prior EXTRA_STOP_WORDS. "schlerinnen"/"schler"/"fr" were an
# undocumented band-aid for the font-encoding corruption bug fixed at its
# source in keyword_search.py (METHODOLOGY.md SS1) -- kept here only as a
# defensive fallback in case an undiscovered document has the same issue,
# not as the primary fix.
LEGACY_ARTIFACT_STOPWORDS_DE: frozenset[str] = frozenset({
    "gv", "lt", "ca", "tf", "ak", "le", "sowie", "usw", "vgl",
    "schlerinnen", "schler", "fr",
})

BASE_STOPWORDS_DE: frozenset[str] = (
    frozenset(w.lower() for w in _SPACY_DE_STOP_WORDS)
    | ADMIN_STOPWORDS_DE
    | LEGACY_ARTIFACT_STOPWORDS_DE
)


def _load_concept_seed_terms() -> dict[str, set[str]]:
    """Map each concept lemma to its own keyword variants (lowercased),
    for Tier 3 per-concept self-seed exclusion (METHODOLOGY.md SS2): by
    construction ~100% of a concept's own documents contain its seed
    term, so it must be excluded from that concept's OWN vectorizer --
    but stays available as ordinary vocabulary in every other concept's
    model, where it may be genuinely informative.
    """
    seeds: dict[str, set[str]] = {}
    with open(KEYWORDS_PATH, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            variants = [v.strip() for v in line.split(",") if v.strip()]
            if not variants:
                continue
            lemma = variants[0]
            seeds[lemma] = {v.lower() for v in variants}
    return seeds


CONCEPT_SEED_TERMS: dict[str, set[str]] = _load_concept_seed_terms()


def stopwords_for_concept(concept: str) -> frozenset[str]:
    """Base stopwords (Tier 1 + generic German + legacy artifacts) plus
    this concept's own seed-term variants (Tier 3) -- the vocabulary to
    exclude when fitting that concept's own topic model. Concepts not
    found in keywords.txt get the base list unchanged.
    """
    seed = CONCEPT_SEED_TERMS.get(concept, set())
    return frozenset(BASE_STOPWORDS_DE | seed)
