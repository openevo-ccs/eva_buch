#!/usr/bin/env python3
# ══════════════════════════════════════════════════════════════════════════
#  compute_cross_concept_analytics.py
# ──────────────────────────────────────────────────────────────────────────
#  Two analyses the app_specs.md LDA section asks for that need every
#  concept's output together, so they live in their own pass after the main
#  per-concept pipeline (lda_topic_model.py) has produced topic_terms and
#  doc_top_topics for every concept x n_topics combination.
#
#  1. Concept co-occurrence — for each pair of concepts (i, j): in how many
#     of concept i's topics does concept j's own search term appear among
#     the topic's top salient terms? Uses the k=10 run's topic_terms CSV
#     (already the top-20-terms-per-topic table) as the source per concept.
#     This replaces the site's previous placeholder, which only counted
#     coincidental overlap of generic topic *labels* between concepts.
#
#  2. Topic distribution by subject — per concept x k, a topics x subjects
#     cross-tab with a totals column, derived from each run's
#     doc_top_topics_{concept}_{k}.csv (which already carries `subject` and
#     `most_prevalent_topic_id` per excerpt).
#
#  Scope: the same 22 concepts app_specs.md lists for both the BERTopic and
#  LDA sections (bertopic/src/data/manifest.json's concept_order) — not the
#  full ~29-concept keyword list in lda_topic_modelling/in/, which includes
#  extra exploratory concepts outside the published scope.
#
#  OUTPUTS
#  -------
#    lda_topic_modelling/out/concept_cooccurrence.json
#    lda_topic_modelling/out/{concept}/{k}/topic_distribution_by_subject_{concept}_{k}.csv
# ══════════════════════════════════════════════════════════════════════════

import json
import sys
from pathlib import Path

import pandas as pd

sys.path.append(str(Path(__file__).parent.parent.parent))
from config import LDA_OUT as OUT_DIR, TM_DIR

N_TOPICS_LIST = [5, 7, 10]
COOCCURRENCE_K = 10
BERTOPIC_MANIFEST = TM_DIR / "src" / "data" / "manifest.json"


def load_canonical_concepts() -> list[str]:
    with open(BERTOPIC_MANIFEST, encoding="utf-8") as f:
        manifest = json.load(f)
    return manifest["concept_order"]


def compute_cooccurrence(concepts: list[str]) -> dict:
    term_sets_per_topic: dict[str, list[set[str]]] = {}
    for concept in concepts:
        path = OUT_DIR / concept / str(COOCCURRENCE_K) / f"topic_terms_{concept}_{COOCCURRENCE_K}.csv"
        if not path.exists():
            print(f"  [WARN] Missing {path}, treating '{concept}' as having no terms.")
            term_sets_per_topic[concept] = []
            continue
        df = pd.read_csv(path, encoding="utf-8")
        term_sets_per_topic[concept] = [set(df[col].dropna().str.lower()) for col in df.columns]

    matrix = []
    for row_concept in concepts:
        row_lemma_sets = term_sets_per_topic[row_concept]
        row = []
        for col_concept in concepts:
            col_lemma = col_concept.lower()
            count = sum(1 for term_set in row_lemma_sets if col_lemma in term_set)
            row.append(count)
        matrix.append(row)

    return {"concepts": concepts, "k": COOCCURRENCE_K, "matrix": matrix}


def compute_topic_distribution_by_subject(concept: str, n_topics: int) -> None:
    out_dir = OUT_DIR / concept / str(n_topics)
    doc_topics_path = out_dir / f"doc_top_topics_{concept}_{n_topics}.csv"
    if not doc_topics_path.exists():
        print(f"  [WARN] Missing {doc_topics_path}, skipping.")
        return

    df = pd.read_csv(doc_topics_path, encoding="utf-8")
    subjects = sorted(s for s in df["subject"].dropna().unique().tolist())

    pivot = pd.crosstab(df["most_prevalent_topic_id"], df["subject"])
    pivot = pivot.reindex(columns=subjects, fill_value=0)
    pivot = pivot.reindex(range(1, n_topics + 1), fill_value=0)
    pivot.insert(0, "topic_id", pivot.index)
    pivot["total"] = pivot[subjects].sum(axis=1)
    pivot.to_csv(out_dir / f"topic_distribution_by_subject_{concept}_{n_topics}.csv", index=False)


def main() -> None:
    concepts = load_canonical_concepts()
    print(f"{len(concepts)} canonical concepts loaded from {BERTOPIC_MANIFEST}.")

    print("Computing concept co-occurrence matrix …")
    cooccurrence = compute_cooccurrence(concepts)
    out_path = OUT_DIR / "concept_cooccurrence.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(cooccurrence, f, ensure_ascii=False, indent=2)
    print(f"  Wrote {out_path}")

    print("Computing topic distribution by subject for every concept x n_topics …")
    for concept in concepts:
        for n_topics in N_TOPICS_LIST:
            compute_topic_distribution_by_subject(concept, n_topics)
    print("  Done.")


if __name__ == "__main__":
    main()
