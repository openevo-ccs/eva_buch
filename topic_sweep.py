"""topic_sweep.py -- Topic-count sweep + coherence + BERTopic/LDA agreement
validation infrastructure.

For each concept, evaluates topic quality across a range of K values using
gensim's c_v coherence, for both BERTopic (one natural base fit, then
BERTopic's own reduce_topics() cheaply re-merges down to each K -- reuses
the cached c-TF-IDF hierarchy, no re-embedding/re-clustering) and LDA
(refit from scratch per K -- LDA has no analogous cheap reduction). Also
computes a term-overlap agreement score between the two methods at matched
K: convergence between two structurally different unsupervised methods is
evidence the discovered topics reflect real corpus structure rather than a
method-specific artifact; divergence flags a concept for cautious
interpretation.

Approved 2026-07-21 (METHODOLOGY.md section 4): run across all 22 concepts,
not just the 3 flagship ones (Verhalten/Mensch/Evolution).

This module does NOT run automatically -- sweep_concept() evaluates one
concept (useful for ad-hoc testing on a cheap concept first), and
run_full_sweep() / the CLI entrypoint runs all requested concepts. This is
the expensive step of Phase 3 (refits/re-merges every concept at every K
for both methods) -- invoke deliberately, not as a side effect of anything
else.

Usage:
    python topic_sweep.py --concepts Vorurteil --k-values 5,7,10
    python topic_sweep.py --concepts all --out out/topic_sweep_report.json
"""

from __future__ import annotations

import argparse
import copy
import json
import logging
import re
import sys
import warnings
from pathlib import Path
from typing import Any, Optional

warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.append(str(ROOT))
sys.path.append(str(ROOT / "bertopic" / "src"))
sys.path.append(str(ROOT / "lda_topic_modelling" / "src"))

from shared_stopwords import stopwords_for_concept  # noqa: E402
import bertopic_pipeline_v2 as bt  # noqa: E402
import lda_topic_model as lda  # noqa: E402

DEFAULT_K_VALUES: tuple[int, ...] = (5, 7, 10, 12, 15, 20)
TOPN_TERMS_FOR_COHERENCE = 10


def _null_logger() -> logging.Logger:
    log = logging.getLogger("topic_sweep")
    if not log.handlers:
        log.addHandler(logging.NullHandler())
    log.setLevel(logging.WARNING)
    return log


def _tokenize_for_coherence(docs: list[str], stopwords: frozenset[str]) -> list[list[str]]:
    """Tokenize raw excerpt text into the word lists gensim's coherence
    model needs as its reference corpus -- the same token pattern
    BERTopic's vectorizer uses, filtered through the same shared stopword
    list so coherence is evaluated on the vocabulary the topics were
    actually built from.
    """
    token_pattern = re.compile(r"(?u)\b[^\W\d_]{3,}\b")
    return [
        [t for t in token_pattern.findall(doc.lower()) if t not in stopwords]
        for doc in docs
    ]


def bertopic_terms_at_k(
    topic_model: "bt.BERTopic", docs: list[str], k: int, topn: int = TOPN_TERMS_FOR_COHERENCE,
) -> list[list[str]]:
    """Cheaply re-merge an already-fitted BERTopic model down to <=k topics
    via its own reduce_topics() (reuses the cached c-TF-IDF hierarchy, no
    re-embedding/re-clustering) and return each real (non-outlier) topic's
    top-N terms. Operates on a deepcopy so repeated calls at different K
    don't compound on the same model instance.
    """
    reduced = copy.deepcopy(topic_model)
    reduced.reduce_topics(docs, nr_topics=k)
    term_lists = []
    for topic_id in sorted(set(reduced.topics_)):
        if topic_id == -1:
            continue
        terms = reduced.get_topic(topic_id) or []
        words = [w for w, _ in terms[:topn] if w.strip()]
        if words:
            term_lists.append(words)
    return term_lists


def lda_terms_at_k(
    preprocessed_docs: list[str], k: int, topn: int = TOPN_TERMS_FOR_COHERENCE,
) -> list[list[str]]:
    """Fit a fresh LDA model at k topics (no cheap reduction exists for
    LDA -- must refit) and return each topic's top-N terms.
    """
    n = len(preprocessed_docs)
    min_df = min(5, max(1, n // 20))
    dtm, vectorizer = lda.create_dtm(preprocessed_docs, min_df=min_df, max_df=0.8)
    feature_names = vectorizer.get_feature_names_out()
    model, _ = lda.train_lda(dtm, n_topics=k)
    term_lists = []
    for topic in model.components_:
        top_idx = topic.argsort()[: -topn - 1 : -1]
        words = [feature_names[i] for i in top_idx if feature_names[i].strip()]
        if words:
            term_lists.append(words)
    return term_lists


def coherence_c_v(term_lists: list[list[str]], tokenized_docs: list[list[str]]) -> Optional[float]:
    """gensim c_v coherence over a set of topics' top terms, evaluated
    against the concept's own tokenized corpus. Returns None (not NaN) on
    degenerate input so it's easy to filter out of a report.
    """
    if not term_lists or all(len(t) == 0 for t in term_lists):
        return None
    from gensim.corpora import Dictionary
    from gensim.models.coherencemodel import CoherenceModel

    dictionary = Dictionary(tokenized_docs)
    try:
        cm = CoherenceModel(
            topics=term_lists, texts=tokenized_docs, dictionary=dictionary, coherence="c_v",
        )
        return float(cm.get_coherence())
    except Exception:
        return None


def agreement_score(terms_a: list[list[str]], terms_b: list[list[str]]) -> Optional[float]:
    """Best-match average Jaccard similarity between two methods' topic
    term sets at the same K -- optimal one-to-one assignment (Hungarian
    algorithm) so each topic is matched to its closest counterpart in the
    other method, then averaged. 1.0 = identical term sets; near 0 = no
    overlap (method artifact, treat the shared K's structure cautiously).
    """
    if not terms_a or not terms_b:
        return None
    from scipy.optimize import linear_sum_assignment

    sets_a = [set(t) for t in terms_a]
    sets_b = [set(t) for t in terms_b]
    n, m = len(sets_a), len(sets_b)
    cost = np.zeros((n, m))
    for i, sa in enumerate(sets_a):
        for j, sb in enumerate(sets_b):
            union = sa | sb
            jaccard = len(sa & sb) / len(union) if union else 0.0
            cost[i, j] = 1.0 - jaccard
    row_ind, col_ind = linear_sum_assignment(cost)
    similarities = [1.0 - cost[r, c] for r, c in zip(row_ind, col_ind)]
    return float(np.mean(similarities)) if similarities else None


def sweep_concept(
    concept: str,
    df: pd.DataFrame,
    embeddings_all: np.ndarray,
    k_values: tuple[int, ...] = DEFAULT_K_VALUES,
    cache_dir: Path = ROOT / "bertopic" / "src" / "cache",
    log: Optional[logging.Logger] = None,
) -> dict[str, Any]:
    """Run the full K-sweep for one concept. Returns a JSON-serializable
    report: per-K BERTopic/LDA coherence and topic counts, plus their
    term-overlap agreement.
    """
    log = log or _null_logger()
    meta_df = bt.get_concept_documents(df, concept)
    docs = meta_df[bt.COLUMN_MAP["text"]].astype(str).tolist()
    if len(docs) == 0:
        return {"concept": concept, "error": "no matching documents"}

    embeddings = embeddings_all[meta_df["doc_id"].to_numpy()]
    stopwords = stopwords_for_concept(concept)
    tokenized = _tokenize_for_coherence(docs, stopwords)

    # One natural BERTopic fit (uncapped -- nr_topics=None), reused for
    # every K in the sweep via cheap reduce_topics() calls below.
    topic_model, _ = bt.fit_or_load_bertopic(
        concept, docs, embeddings, cache_dir, log, nr_topics=None, force=False,
    )

    excerpts = [{"text_excerpt": d} for d in docs]
    lda_preprocessed = lda.preprocess_text(excerpts, concept)

    report: dict[str, Any] = {"concept": concept, "n_docs": len(docs), "k_values": {}}
    for k in k_values:
        bt_terms = bertopic_terms_at_k(topic_model, docs, k)
        lda_terms = lda_terms_at_k(lda_preprocessed, k)
        report["k_values"][str(k)] = {
            "bertopic_n_real_topics": len(bt_terms),
            "bertopic_coherence_cv": coherence_c_v(bt_terms, tokenized),
            "lda_n_topics": len(lda_terms),
            "lda_coherence_cv": coherence_c_v(lda_terms, tokenized),
            "agreement_jaccard": agreement_score(bt_terms, lda_terms),
        }
    return report


def _load_existing_reports(out_path: Optional[Path]) -> dict[str, dict[str, Any]]:
    if out_path is None or not out_path.exists():
        return {}
    with open(out_path, "r", encoding="utf-8") as f:
        existing = json.load(f)
    return {r["concept"]: r for r in existing if "concept" in r}


def _write_reports(out_path: Path, reports_by_concept: dict[str, dict[str, Any]]) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = out_path.with_suffix(out_path.suffix + ".tmp")
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(list(reports_by_concept.values()), f, ensure_ascii=False, indent=2)
    tmp_path.replace(out_path)


def run_full_sweep(
    concepts: list[str],
    csv_path: Path,
    k_values: tuple[int, ...] = DEFAULT_K_VALUES,
    cache_dir: Path = ROOT / "bertopic" / "src" / "cache",
    out_path: Optional[Path] = None,
    resume: bool = True,
) -> list[dict[str, Any]]:
    """Run sweep_concept() across multiple concepts, reusing one global
    embeddings matrix (the expensive shared step) across all of them.

    If out_path is given, the report is written after every concept
    (not just once at the end) so a mid-run interruption loses at most
    one concept's worth of work. If resume is True and out_path already
    holds results, concepts already present there are skipped.
    """
    log = _null_logger()
    df = bt.load_source_csv(csv_path, log)
    embeddings_all = bt.compute_or_load_embeddings(
        df[bt.COLUMN_MAP["text"]].astype(str).tolist(), cache_dir, log, force=False,
    )
    reports_by_concept = _load_existing_reports(out_path) if resume else {}
    for concept in concepts:
        if concept in reports_by_concept:
            print(f"--- skipping {concept} (already in {out_path}) ---")
            continue
        print(f"--- sweeping {concept} ---")
        reports_by_concept[concept] = sweep_concept(
            concept, df, embeddings_all, k_values, cache_dir, log,
        )
        if out_path is not None:
            _write_reports(out_path, reports_by_concept)
    return [reports_by_concept[c] for c in concepts if c in reports_by_concept]


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--concepts", type=str, default="all",
                    help="Comma-separated concept list, or 'all' for the 22 default concepts.")
    p.add_argument("--k-values", type=str, default=",".join(str(k) for k in DEFAULT_K_VALUES),
                    help="Comma-separated topic counts to sweep.")
    p.add_argument("--csv", type=Path, default=ROOT / "keyword_search" / "out" / "results.csv")
    p.add_argument("--out", type=Path, default=ROOT / "bertopic" / "src" / "out" / "topic_sweep_report.json")
    p.add_argument("--no-resume", action="store_true",
                    help="Ignore any existing --out file and re-sweep every requested concept.")
    args = p.parse_args()

    concepts = bt.DEFAULT_CONCEPTS if args.concepts == "all" else [
        c.strip() for c in args.concepts.split(",") if c.strip()
    ]
    k_values = tuple(int(k) for k in args.k_values.split(",") if k.strip())

    run_full_sweep(concepts, args.csv, k_values, out_path=args.out, resume=not args.no_resume)
    print(f"Wrote sweep report -> {args.out}")


if __name__ == "__main__":
    main()
