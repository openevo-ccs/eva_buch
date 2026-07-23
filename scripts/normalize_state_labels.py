#!/usr/bin/env python3
"""Apply the shared state-name normalisation (shared_state_normalization.py)
to the already-generated keyword_search outputs, in place.

get_meta() in keyword_search.py now canonicalizes state names at the source
for future runs, but the currently-committed results.csv/doc_word_counts.csv
still carry the raw abbreviations from before that fix (BaWü, MeckPomm, NRW,
None). Re-running the full keyword_search pipeline (PDF extraction + search
across 295 documents) just to pick up a metadata-column fix is unnecessary --
this script normalizes the existing CSVs directly and rebuilds
state_subject_count_matrix.csv from the corrected data, reusing
keyword_search.py's own make_pivot() so the aggregation logic isn't
duplicated.

Usage:
    python scripts/normalize_state_labels.py [--dry-run]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT / "keyword_search" / "src"))
sys.path.append(str(ROOT))

import pandas as pd  # noqa: E402
import keyword_search as ks  # noqa: E402
from shared_state_normalization import canonicalize_state  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true",
                         help="Report what would change without writing files.")
    args = parser.parse_args()

    results_path = ks.OUT_DIR / "results.csv"
    counts_path = ks.OUT_DIR / "doc_word_counts.csv"

    results_df = pd.read_csv(results_path)
    counts_df = pd.read_csv(counts_path)

    before = sorted(str(v) for v in set(results_df["state"].unique()) | set(counts_df["state"].unique()))

    for df in (results_df, counts_df):
        df["state"] = df["state"].apply(lambda raw: canonicalize_state(raw, ks.UNMAPPED_STATES))

    after = sorted(str(v) for v in set(results_df["state"].unique()) | set(counts_df["state"].unique()))

    print("Raw state values before:", before)
    print("Canonical state values after:", after)
    if ks.UNMAPPED_STATES:
        print(f"[WARN] {len(ks.UNMAPPED_STATES)} unmapped state value(s): {dict(ks.UNMAPPED_STATES)}")

    if args.dry_run:
        print("[dry-run] No files written.")
        return

    results_df.to_csv(results_path, index=False)
    counts_df.to_csv(counts_path, index=False)
    print(f"Wrote {results_path}")
    print(f"Wrote {counts_path}")

    ks.make_pivot(results_df, "state", "subject")
    print(f"Wrote {ks.OUT_DIR / 'state_subject_count_matrix.csv'}")


if __name__ == "__main__":
    main()
