# Phase 1 Audit — Corruption Root Cause + Stopword Term-Frequency Review

Working notes from the Phase 1 diagnostics of the data-rerun plan. For Susan's review before Phase 2 (fix implementation) starts.

---

## 1. Umlaut-corruption bug — root cause found, fully scoped

**Root cause:** exactly **one** source document, `LP RheinPfalz Philosohpie Gym Sek2.pdf` (Ethik/Philo, Rheinland-Pfalz, Gymnasium Sek II), uses an embedded font with a broken/non-standard character-encoding table. When `pymupdf` extracts its text, German special characters are silently mis-mapped to the wrong Unicode characters instead of being extracted correctly:

| Correct character | Extracted as | Occurrences in this document |
|---|---|---|
| ü | Ÿ (U+0178) | 544 |
| ä | Š (U+0160) | 463 |
| ö (likely) | š (U+0161) | 138 |
| ß (likely) | ã (U+00E3) | 42 |

This is a known class of PDF quirk: an old document with a font subset lacking a proper ToUnicode CMap, so the text-extraction library falls back to a wrong glyph→Unicode guess. It is **not** a bug in pymupdf usage generally, and **not** present in any of the other 294 source documents (verified by scanning all raw `.txt` mirrors for the telltale Ÿ/Š/š characters — only this one file matches).

**Why it looked worse than "one document":** `keyword_search.py`'s `clean_hyphenated_text()` whitelist-strips any character outside `[a-zA-ZäöüÄÖÜßéèêëçñ\s,.;:/-]` — so once the font bug mis-maps ü→Ÿ, that step silently *deletes* the Ÿ entirely (Ÿ isn't in the whitelist), turning "Schüler" into "Schler" rather than preserving or flagging it. That's how a single mis-encoded document became 57+ visibly corrupted excerpts propagating into both the BERTopic and LDA pipelines (both consume `results.csv`'s `text_excerpt`) and, from there, into topic labels shown in the live app. Someone already noticed the symptom and patched around it — `bertopic_pipeline_v2.py`'s `EXTRA_STOP_WORDS` contains `"schlerinnen", "schler", "fr"`, the corrupted forms — without ever finding the source.

**Recommended fix (two parts):**
1. **Targeted repair for this one document**: either (a) re-extract it with a manual character remap applied before the whitelist filter (Ÿ→ü, Š→ä, š→ö, ã→ß, verified against the source PDF's actual content), or (b) if remapping proves unreliable, re-OCR just this one PDF (cheap — it's 1 of 295).
2. **Defensive fix in the pipeline**: change `clean_hyphenated_text()` to *log* (not silently drop) any character it strips that isn't whitespace/punctuation, so a future document with the same font issue is caught by inspection rather than discovered by accident months later. This is a few lines, not a redesign.

Cost: trivial. This does not require touching the other 294 documents.

---

## 2. Stopword term-frequency audit

Tokenized all 35,893 excerpts in `results.csv` (2,009,632 token occurrences, 45,611 distinct terms) using the same tokenization BERTopic already uses, and checked each of the top 400 most frequent terms against both pipelines' current stopword lists (NLTK German + BERTopic's 15 extras; spaCy German + LDA's 26 extras).

**Key numbers:** the "Kompetenz" word family alone — `kompetenzen` (4,913), `kompetenzerwartungen` (1,496), `sachkompetenz` (939), `kompetenz` (925), `urteilskompetenz` (767), `methodenkompetenz` (734), `handlungskompetenz` (693) — totals **10,467 occurrences**, filtered by **neither** pipeline's stopword list. Curriculum-standard boilerplate at that volume is very likely diluting topic labels across most/all 22 concepts.

The audit surfaces three distinct tiers that need to be handled differently — **this distinction matters a lot**, because a naive "stopword everything frequent and uncovered" pass would delete the actual subject matter of the study:

### Tier 1 — Add to a shared stopword list (genuine administrative/pedagogical noise)
Curriculum-document scaffolding, not conceptual content:
`schülerinnen`, `schüler` (already in LDA's list, missing from BERTopic's), `kompetenz`, `kompetenzen`, `kompetenzerwartungen`, `sachkompetenz`, `urteilskompetenz`, `methodenkompetenz`, `handlungskompetenz`, `unterricht`, `fach`, `themen`, `hinweise`, `bildung`, `grundlage`, `grundlagen`, `aspekte`, `bezüge`, `lernenden` *(as the noun "learners" — see Tier 2 caveat on "lernen")*.

Plus the German Bildungsstandards' standard competency-verbs ("Operatoren") — generic assessment-instruction verbs that appear in nearly every curriculum statement regardless of topic: `erläutern`, `beschreiben`, `beurteilen`, `reflektieren`, `analysieren`, `erklären`, `bewerten`, `erkennen`, `diskutieren`, `vergleichen`, `unterscheiden`, `darstellen`, `kennen`.

### Tier 2 — Must NOT be stopworded (target concepts / substantive content, despite high frequency)
These are exactly the words the analysis is about, or closely adjacent to it: `menschen`/`mensch` (concept **Mensch**), `handeln`/`handelns`/`handlungen` (concept **Handeln**), `normen` (concept **Norm**), `werte`/`werten` (concept **Wert**), `freiheit` (concept **Freiheit**), `gerechtigkeit` (concept **Gerechtigkeit**), `verhalten` (concept **Verhalten**), `evolution` (concept **Evolution**), `glück` (concept **Glück**), `kultur` (concept **Kultur**), `moral`/`moralische` (concept **Moral**), plus adjacent substantive vocabulary: `demokratie`, `gesellschaft`, `ethik`, `welt`, `natur`, `geschichte`, `zukunft`, `verantwortung`, `entwicklung`. `lernen` is ambiguous — it's both a generic verb and its own concept in the broader 79-term keyword list; needs a judgment call, leaning toward keeping it.

### Tier 3 — Per-concept self-seed exclusion (not a global stopword)
Each concept's own keyword variants (from `keywords.txt`) should be excluded **only from that concept's own topic vectorizer**, not globally — e.g. strip "freiheit"/"autonomie" from the Freiheit model's vocabulary (since by construction ~100% of its documents contain it, so it's a trivial dominant term there), while leaving "freiheit" available as ordinary vocabulary in every *other* concept's model, where it may be genuinely informative (e.g. if it co-occurs meaningfully in Gerechtigkeit's topics).

---

## Decisions — approved 2026-07-21
1. **Tier 1 stopword-addition list** — approved as written above.
2. **Tier 2 exceptions** — confirmed correct; these stay in vocabulary. This resolves the one open ambiguity noted for `lernen`: keep it (treat as Tier 2, not stopworded).
3. **Tier 3 per-concept self-seed exclusion** — approved as described.
4. **Corruption fix for the one affected document** — remap preferred; fall back to re-OCR only if the character remap proves unreliable once attempted against the actual PDF.

All four are now unblocked for Phase 2 implementation.
