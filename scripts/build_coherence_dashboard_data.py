#!/usr/bin/env python3
"""
Aggregates already-computed per-concept BERTopic/LDA output into one
consolidated JSON for the Kohaerenz (coherence) dashboard -- the app's
"vertical/horizontal coherence" diagnostic view, one screen per concept
instead of four separate method pages a reader has to synthesize
themselves.

Deliberately computes nothing new: every number here already exists in
bertopic/src/out/{concept}/dist_topics_over_subjects_{concept}.csv (incl.
a per-topic subject-entropy column -- high entropy = a topic's documents
are spread across many subjects, i.e. a candidate interdisciplinary
"bridge" topic; low entropy = concentrated in one subject, i.e. siloed),
bertopic/src/data/manifest.json (per-concept subject/state coverage), the
per-concept JSON (grade_band per document), and
lda_topic_modelling/out/concept_cooccurrence.json (cross-concept
relatedness). This script only reshapes and ranks what's already there.

Usage:
    python scripts/build_coherence_dashboard_data.py
"""
from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BERTOPIC_DATA = ROOT / "bertopic" / "src" / "data"
BERTOPIC_OUT = ROOT / "bertopic" / "src" / "out"
LDA_OUT = ROOT / "lda_topic_modelling" / "out"

GRADE_BAND_ORDER = ["1-4", "5-6", "7-8", "9-10", "11-13"]
TOP_BRIDGE_TOPICS = 6
TOP_RELATED_CONCEPTS = 5


def load_manifest() -> dict:
    with open(BERTOPIC_DATA / "manifest.json", encoding="utf-8") as f:
        return json.load(f)


def load_cooccurrence() -> dict | None:
    path = LDA_OUT / "concept_cooccurrence.json"
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def related_concepts_for(concept: str, cooc: dict | None) -> list[dict]:
    if not cooc:
        return []
    concepts = cooc["concepts"]
    matrix = cooc["matrix"]
    if concept not in concepts:
        return []
    idx = concepts.index(concept)
    row = matrix[idx]
    scored = [
        {"concept": other, "score": row[j]}
        for j, other in enumerate(concepts)
        if other != concept and row[j] > 0
    ]
    scored.sort(key=lambda r: -r["score"])
    return scored[:TOP_RELATED_CONCEPTS]


def grade_band_counts(concept: str) -> dict[str, int]:
    path = BERTOPIC_DATA / f"{concept}.json"
    with open(path, encoding="utf-8") as f:
        records = json.load(f)
    counts = Counter(r.get("grade_band", "?") for r in records if not r.get("is_outlier"))
    return {band: counts.get(band, 0) for band in GRADE_BAND_ORDER if counts.get(band, 0) > 0} | {
        band: c for band, c in counts.items() if band not in GRADE_BAND_ORDER
    }


def topic_rows(concept: str) -> list[dict]:
    path = BERTOPIC_OUT / concept / f"dist_topics_over_subjects_{concept}.csv"
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        subject_cols = [c for c in reader.fieldnames if c not in
                        ("topic_name", "entropy", "topic_total", "topic_proportion")]
        rows = []
        for row in reader:
            name = row["topic_name"].strip()
            # Skip the summary row and the HDBSCAN outlier bucket -- the
            # latter is technically often the highest-entropy "topic"
            # (it absorbs leftover documents from every subject), but
            # that's a clustering artifact, not an interdisciplinary
            # finding, and would misleadingly top every bridge-topic list.
            if name.lower() in ("gesamt", "total") or name.startswith("Kein Thema"):
                continue
            subj_dist = {s: float(row[s]) for s in subject_cols if row[s]}
            n_subjects_present = sum(1 for v in subj_dist.values() if v > 0)
            rows.append({
                "label": row["topic_name"],
                "entropy": round(float(row["entropy"]), 4) if row["entropy"] else 0.0,
                "topic_total": int(float(row["topic_total"])) if row["topic_total"] else 0,
                "topic_proportion": round(float(row["topic_proportion"]), 4) if row["topic_proportion"] else 0.0,
                "subject_distribution": subj_dist,
                "n_subjects_present": n_subjects_present,
            })
        return rows


def build() -> None:
    manifest = load_manifest()
    cooc = load_cooccurrence()
    concepts = manifest["concept_order"]

    out: dict[str, dict] = {}
    for concept in concepts:
        cm = manifest["concepts"][concept]
        topics = topic_rows(concept)
        bridge_topics = sorted(
            (t for t in topics if t["n_subjects_present"] >= 2),
            key=lambda t: (-t["entropy"], -t["topic_total"]),
        )[:TOP_BRIDGE_TOPICS]
        siloed_topics = sorted(
            (t for t in topics if t["n_subjects_present"] == 1),
            key=lambda t: -t["topic_total"],
        )[:TOP_BRIDGE_TOPICS]

        out[concept] = {
            "concept": concept,
            "n_docs": cm["n_docs"],
            "n_outliers": cm["n_outliers"],
            "subjects": cm["subjects"],
            "n_subjects": len(cm["subjects"]),
            "n_subjects_total": 5,
            "n_states": len(cm["states"]),
            "n_states_total": 16,
            "grade_bands": grade_band_counts(concept),
            "n_topics": len(topics),
            "bridge_topics": bridge_topics,
            "siloed_topics": siloed_topics,
            "related_concepts": related_concepts_for(concept, cooc),
        }
        print(f"[{concept}] {len(topics)} topics, {len(bridge_topics)} bridge, "
              f"{len(siloed_topics)} siloed, {len(out[concept]['related_concepts'])} related")

    out_path = BERTOPIC_DATA / "coherence_dashboard.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    build()
