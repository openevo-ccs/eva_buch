#!/usr/bin/env python3
"""
Assembles everything docs/data/ needs from the three analysis pipelines'
output folders, in one command, so the deployed GitHub Pages site can't
silently drift from the underlying analysis again.

Copies:
  bertopic/src/data/{*.json, manifest.json, color_maps.json}
    -> docs/data/bertopic/
  lda_topic_modelling/out/{concept}/{5,7,10}/{topic_terms, term_frequency_matrix,
  ldavis_data, topic_distribution_by_subject, stats/*}
    -> docs/data/lda/{concept}/{k}/
  lda_topic_modelling/out/concept_cooccurrence.json
    -> docs/data/lda/concept_cooccurrence.json
  keyword_search/out/{results.csv, doc_word_counts.csv,
  state_subject_count_matrix.csv}
    -> docs/data/
  data/LP_DE_2026_1_txtfiles/
    -> docs/data/txtfiles/ (raw corpus mirror, so the Lehrplandokumente table
       can link to full document text on GitHub Pages)

LDA/BERTopic scope is the 22 canonical concepts from
bertopic/src/data/manifest.json's concept_order (the same list
app_specs.md lists for both sections) -- lda_topic_modelling/out/ also
contains a few extra exploratory concepts outside that published scope,
which are intentionally left out of docs/data/.

document_catalog.json is maintained separately by
scripts/generate_document_catalog.py (it reads the raw text corpus, not a
pipeline "out" folder, so it isn't part of this script).

Prerequisites (run once beforehand, or after re-running the pipelines):
  python bertopic/src/bertopic_pipeline_v2.py
  python bertopic/src/build_global_projection.py
  python bertopic/src/viz_umap_2d_v2.py --force-color-maps
  python lda_topic_modelling/src/lda_topic_model.py
  python lda_topic_modelling/src/compute_cross_concept_analytics.py

Usage:
  python scripts/build_docs_data.py
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BERTOPIC_DATA = ROOT / "bertopic" / "src" / "data"
LDA_OUT = ROOT / "lda_topic_modelling" / "out"
KEYWORD_OUT = ROOT / "keyword_search" / "out"
DOCS_DATA = ROOT / "docs" / "data"
TXTFILES_SRC = ROOT / "data" / "LP_DE_2026_1_txtfiles"

N_TOPICS_LIST = [5, 7, 10]

LDA_FILES_PER_RUN = [
    "topic_terms_{concept}_{k}.csv",
    "term_frequency_matrix_{concept}_{k}.csv",
    "ldavis_data_{concept}_{k}.json",
    "topic_distribution_by_subject_{concept}_{k}.csv",
]
LDA_STATS_FILES = [
    "global_summary_{concept}_{k}.csv",
    "topic_summary_{concept}_{k}.csv",
]


def build_bertopic_data() -> list[str]:
    target = DOCS_DATA / "bertopic"
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)

    manifest_path = BERTOPIC_DATA / "manifest.json"
    if not manifest_path.exists():
        raise SystemExit(f"[FATAL] {manifest_path} not found -- run bertopic_pipeline_v2.py first.")

    for name in ("manifest.json", "color_maps.json"):
        src = BERTOPIC_DATA / name
        if src.exists():
            shutil.copy2(src, target / name)
        else:
            print(f"  [WARN] Missing {src}.")

    with open(manifest_path, encoding="utf-8") as f:
        concepts = json.load(f)["concept_order"]

    copied = 0
    for concept in concepts:
        src = BERTOPIC_DATA / f"{concept}.json"
        if src.exists():
            shutil.copy2(src, target / f"{concept}.json")
            copied += 1
        else:
            print(f"  [WARN] Missing bertopic data for '{concept}'.")
    print(f"BERTopic: copied {copied}/{len(concepts)} concept files -> {target}")
    return concepts


def build_lda_data(concepts: list[str]) -> None:
    target = DOCS_DATA / "lda"
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)

    cooccurrence_src = LDA_OUT / "concept_cooccurrence.json"
    if cooccurrence_src.exists():
        shutil.copy2(cooccurrence_src, target / "concept_cooccurrence.json")
    else:
        print("  [WARN] concept_cooccurrence.json not found -- run compute_cross_concept_analytics.py first.")

    copied = 0
    missing_runs = 0
    for concept in concepts:
        for k in N_TOPICS_LIST:
            src_dir = LDA_OUT / concept / str(k)
            if not src_dir.exists():
                missing_runs += 1
                continue
            dst_dir = target / concept / str(k)
            dst_dir.mkdir(parents=True, exist_ok=True)

            for pattern in LDA_FILES_PER_RUN:
                filename = pattern.format(concept=concept, k=k)
                src = src_dir / filename
                if src.exists():
                    shutil.copy2(src, dst_dir / filename)
                    copied += 1

            stats_dir = src_dir / "stats"
            if stats_dir.exists():
                dst_stats = dst_dir / "stats"
                dst_stats.mkdir(exist_ok=True)
                for pattern in LDA_STATS_FILES:
                    filename = pattern.format(concept=concept, k=k)
                    src = stats_dir / filename
                    if src.exists():
                        shutil.copy2(src, dst_stats / filename)
                        copied += 1

    print(f"LDA: copied {copied} files across {len(concepts)} concepts x {len(N_TOPICS_LIST)} topic counts "
          f"({missing_runs} concept x k runs missing entirely) -> {target}")


def build_keyword_search_data() -> None:
    DOCS_DATA.mkdir(parents=True, exist_ok=True)
    files = ["results.csv", "doc_word_counts.csv", "state_subject_count_matrix.csv"]
    copied = 0
    for name in files:
        src = KEYWORD_OUT / name
        if src.exists():
            shutil.copy2(src, DOCS_DATA / name)
            copied += 1
        else:
            print(f"  [WARN] Missing {src}.")
    print(f"Keyword search: copied {copied}/{len(files)} files -> {DOCS_DATA}")


def build_txtfiles_mirror() -> None:
    """Mirror the raw .txt corpus into docs/data/txtfiles/ so the Lehrplandokumente
    table (per app_specs.md) can link straight to a document's full text on the
    deployed GitHub Pages site -- data/LP_DE_2026_1_txtfiles/ itself lives outside
    docs/ and is not served by Pages."""
    target = DOCS_DATA / "txtfiles"
    if not TXTFILES_SRC.exists():
        print(f"  [WARN] {TXTFILES_SRC} not found -- skipping txtfiles mirror.")
        return
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(TXTFILES_SRC, target)
    count = sum(1 for _ in target.rglob("*.txt"))
    print(f"Txtfiles: mirrored {count} file(s) -> {target}")


def main() -> None:
    concepts = build_bertopic_data()
    build_lda_data(concepts)
    build_keyword_search_data()
    build_txtfiles_mirror()
    print("DONE.")


if __name__ == "__main__":
    main()
