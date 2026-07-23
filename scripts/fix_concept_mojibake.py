#!/usr/bin/env python3
"""Fix a small, confirmed mojibake corruption in keyword_search's own output,
found while auditing state-label normalization (2026-07-23).

results.csv/term_count.csv carry two "search_term" values as mojibake
duplicates of the correct concept name -- "RationalitÃ¤t" (4 rows) alongside
the correct "Rationalität" (279 rows), and "EudÃ¤monia" (1 row) alongside
"Eudämonia" (15 rows). keywords.txt itself is confirmed clean UTF-8 (only
U+00E4 'ä', no mojibake bytes), and the corruption affects only these 5 of
28339 rows -- not a uniform, whole-file default-encoding failure, which rules
out load_concept_dict()'s previously-unspecified `open()` encoding as the
sole explanation, though that call has been hardened to `encoding="utf-8"`
regardless (keyword_search.py, and the equivalent load_keywords() in
bertopic/src/utils.py) since an unspecified encoding is platform-dependent
and was already flagged as the class of bug behind the BERTopic language
default (METHODOLOGY.md §4.6). Most plausible origin: a narrow, single-
concept rerun (execute_search(..., search_term=...)) executed at some past
point under a shell where Python's default text encoding wasn't UTF-8,
producing a handful of duplicate-but-mis-encoded rows alongside the
correctly-encoded bulk run -- but the exact provenance no longer matters for
correctness now that both the count and the row content agree these are the
same concept.

Merges the mojibake rows onto the canonical spelling (same underlying
excerpts, just relabeled) rather than dropping them, then rebuilds
term_count.csv and state_subject_count_matrix.csv from the corrected data.

Usage:
    python scripts/fix_concept_mojibake.py [--dry-run]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT / "keyword_search" / "src"))

import pandas as pd  # noqa: E402
import keyword_search as ks  # noqa: E402

MOJIBAKE_TO_CANONICAL = {
    "RationalitÃ¤t": "Rationalität",
    "EudÃ¤monia": "Eudämonia",
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    results_path = ks.OUT_DIR / "results.csv"
    results_df = pd.read_csv(results_path)

    for bad, good in MOJIBAKE_TO_CANONICAL.items():
        n = (results_df["search_term"] == bad).sum()
        print(f"{bad!r} -> {good!r}: {n} row(s)")

    results_df["search_term"] = results_df["search_term"].replace(MOJIBAKE_TO_CANONICAL)

    if args.dry_run:
        print("[dry-run] No files written.")
        return

    results_df.to_csv(results_path, index=False)
    print(f"Wrote {results_path}")

    ks.count_terms(results_df, ks.KEYWORD_PATH)
    print(f"Wrote {ks.OUT_DIR / 'term_count.csv'}")

    ks.make_pivot(results_df, "state", "subject")
    print(f"Wrote {ks.OUT_DIR / 'state_subject_count_matrix.csv'}")


if __name__ == "__main__":
    main()
