#!/usr/bin/env python3
"""Regenerate the excerpt rows for the one source document affected by the
font-encoding corruption bug (METHODOLOGY.md section 1): "LP RheinPfalz
Philosohpie Gym Sek2.pdf".

Does NOT need the source PDF. results.csv's existing rows for this document
already lost the mis-mapped characters outright (they went through the old,
buggy clean_hyphenated_text() before the remap fix existed), so they can't
be patched in place -- but the raw, unclipped .txt mirror
(data/LP_DE_2026_1_txtfiles/Ethik, Philo/LP RheinPfalz Philosohpie Gym
Sek2.txt) still has the characters *mis-mapped but present*, so re-running
just the match/context-window extraction against that corrected text
recovers everything correctly.

This intentionally reuses keyword_search.py's actual matching logic
(normalize_text, clean_hyphenated_text, search_text_for_term, get_meta)
rather than reimplementing it, so the regenerated rows are produced by
exactly the same code path as every other document -- just fed corrected
input text. The only difference from a from-scratch PDF re-extraction is
that the raw mirror wasn't header/footer-clipped per-page the way
search_pdf_for_terms() clips PDF pages directly; a handful of excerpts
near page boundaries may include a stray header/footer word that a true
PDF re-extraction would have clipped. Documented, accepted tradeoff (see
METHODOLOGY.md section 1) rather than requiring the source PDF.

Usage:
    python scripts/fix_rheinpfalz_philosophie_corruption.py [--dry-run]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT / "keyword_search" / "src"))

import pandas as pd  # noqa: E402
import keyword_search as ks  # noqa: E402

AFFECTED_FILE = "LP RheinPfalz Philosohpie Gym Sek2.pdf"
RAW_MIRROR_PATH = ROOT / "data" / "LP_DE_2026_1_txtfiles" / "Ethik, Philo" / "LP RheinPfalz Philosohpie Gym Sek2.txt"
RESULTS_CSV = ROOT / "keyword_search" / "out" / "results.csv"
DOCS_RESULTS_CSV = ROOT / "docs" / "data" / "results.csv"


def regenerate_rows() -> pd.DataFrame:
    """Re-run keyword matching against the corrected raw mirror text for
    the one affected document, across every concept in keywords.txt (not
    just the 22 promoted to BERTopic/LDA -- matching how the original
    full-corpus run searched all of them). Returns a DataFrame in the same
    schema as results.csv.
    """
    if not RAW_MIRROR_PATH.exists():
        raise SystemExit(f"[FATAL] Raw mirror not found: {RAW_MIRROR_PATH}")

    raw_text = RAW_MIRROR_PATH.read_text(encoding="utf-8")
    # This is the actual fix: the raw mirror still carries the mis-mapped
    # (but present) Ÿ/Š/š/ã characters; remap them before anything else runs.
    fixed_text = ks.remap_font_encoding_artifacts(raw_text)
    normalized = ks.normalize_text(fixed_text)

    meta = ks.get_meta(AFFECTED_FILE)
    if not meta:
        raise SystemExit(f"[FATAL] get_meta() rejected filename: {AFFECTED_FILE!r}")

    term_dict = ks.load_concept_dict(ks.KEYWORD_PATH)

    rows: list[dict] = []
    for lemma, terms in term_dict.items():
        for term in terms:
            if not term:
                continue
            matches = ks.search_text_for_term(normalized, lemma, term, context_size=ks.CONTEXT_SIZE)
            for match in matches:
                match.update(meta)
                match["subject"] = "Ethik, Philo"
                rows.append(match)

    return pd.DataFrame(rows)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dry-run", action="store_true",
                    help="Regenerate and report counts/diffs without writing any file.")
    args = p.parse_args()

    print(f"Regenerating excerpt rows for: {AFFECTED_FILE}")
    new_rows = regenerate_rows()
    print(f"  {len(new_rows)} rows regenerated from the corrected raw mirror.")

    # dtype=str + keep_default_na=False: read every field as its literal
    # string, with no numeric/NaN inference. Without this, pandas infers
    # e.g. "year" as float64 (some rows have a missing year) and silently
    # rewrites every "2024" as "2024.0" on the round-trip -- turning a
    # ~350-row content change into a diff touching all 35,893 rows.
    old = pd.read_csv(RESULTS_CSV, low_memory=False, dtype=str, keep_default_na=False)
    old_affected = old[old["file"] == AFFECTED_FILE]
    print(f"  {len(old_affected)} existing (corrupted) rows for this file in {RESULTS_CSV.relative_to(ROOT)}.")

    # Sanity check: the corrected excerpts must not contain any leftover
    # mis-mapped character -- if this fails, do not proceed to write.
    bad_chars = set("ŸŠšã")
    still_bad = new_rows["text_excerpt"].apply(lambda t: bool(bad_chars & set(str(t)))).sum()
    if still_bad:
        raise SystemExit(f"[FATAL] {still_bad} regenerated row(s) still contain mis-mapped characters -- aborting, nothing written.")
    print("  Sanity check passed: zero mis-mapped characters remain in regenerated rows.")

    if args.dry_run:
        print("[DRY RUN] Not writing any file.")
        return

    # Splice the regenerated rows in at the position of the FIRST old row
    # for this file, rather than appending at the end -- keeps every other
    # row's position untouched, so the resulting diff is proportional to
    # what actually changed instead of reordering the entire file.
    affected_mask = old["file"] == AFFECTED_FILE
    first_idx = affected_mask.idxmax() if affected_mask.any() else len(old)
    before = old.iloc[:first_idx]
    after = old.iloc[first_idx:][~affected_mask.iloc[first_idx:]]
    updated = pd.concat(
        [before, new_rows[old.columns.tolist()], after], ignore_index=True,
    )

    for path in (RESULTS_CSV, DOCS_RESULTS_CSV):
        # lineterminator="\n" matches the original file's LF-only line
        # endings -- without this, pandas writes CRLF on Windows and every
        # single line (not just the ~350 that actually changed) shows up
        # as modified in git, which is both misleading for review and
        # bloats the diff/history for no reason.
        updated.to_csv(path, index=False, lineterminator="\n")
        print(f"  Wrote {len(updated):,} total rows -> {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
