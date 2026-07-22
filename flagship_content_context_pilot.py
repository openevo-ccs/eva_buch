"""flagship_content_context_pilot.py -- Content-vs-context test for
Verhalten/Mensch/Evolution (METHODOLOGY.md section 5, item 2).

Strips generic Bildungsstandards competency-verb template language
("Die Schuelerinnen und Schueler [erlaeutern/beurteilen/...] ...") from
excerpt text BEFORE embedding -- not just before vectorizing, which is
where stopwording already happens in the production pipeline. Tests
whether pedagogical "context" phrasing is suppressing "content"
differentiation in the embedding space itself, as originally asked.

Purely comparative: writes to its own cache/out directories, never
touches production data or the production BERTopic cache. Baseline
natural topic counts are read from the already-documented
METHODOLOGY.md section 4.4 table rather than refit here, since that
uncapped fit was already produced and recorded during the K-sweep.

This script does NOT decide anything -- it produces a comparison for
Susan's qualitative read (METHODOLOGY.md section 5, item 3), per the
original design.

Usage:
    python flagship_content_context_pilot.py
"""

from __future__ import annotations

import json
import logging
import re
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

import numpy as np

ROOT = Path(__file__).resolve().parent
sys.path.append(str(ROOT))
sys.path.append(str(ROOT / "bertopic" / "src"))

import bertopic_pipeline_v2 as bt  # noqa: E402

FLAGSHIP_CONCEPTS = ["Verhalten", "Mensch", "Evolution"]

# Natural (uncapped) topic counts already established and documented in
# METHODOLOGY.md section 4.4, read directly from the sweep's cached base
# fits -- not refit here to avoid redundant compute.
BASELINE_NATURAL_TOPICS = {"Verhalten": 22, "Mensch": 90, "Evolution": 22}

CACHE_DIR = ROOT / "bertopic" / "src" / "cache_content_focused"
OUT_DIR = ROOT / "bertopic" / "src" / "out" / "flagship_content_context"

# Terms stripped from RAW excerpt text before embedding (word-boundary,
# case-insensitive). Same Bildungsstandards competency-verb family as
# shared_stopwords.ADMIN_STOPWORDS_DE, but applied to the pre-embedding
# text rather than only at the post-embedding vectorizer stage. German
# verb inflection means a simple stem/form list is an approximation, not
# exhaustive morphological coverage -- documented limitation, not a
# claim of completeness.
STRIP_TERMS = [
    "schülerinnen", "schüler", "schülerin",
    "kompetenz", "kompetenzen", "kompetenzerwartungen",
    "erläutern", "erläutert", "beschreiben", "beschreibt",
    "beurteilen", "beurteilt", "reflektieren", "reflektiert",
    "analysieren", "analysiert", "erklären", "erklärt",
    "bewerten", "bewertet", "erkennen", "erkennt",
    "diskutieren", "diskutiert", "vergleichen", "vergleicht",
    "unterscheiden", "unterscheidet", "darstellen", "stellt dar",
    "kennen", "kennt", "können", "sollen",
]
STRIP_PATTERN = re.compile(
    r"\b(" + "|".join(re.escape(t) for t in STRIP_TERMS) + r")\b",
    re.IGNORECASE,
)


def content_focused_text(text: str) -> str:
    stripped = STRIP_PATTERN.sub(" ", text)
    return re.sub(r"\s+", " ", stripped).strip()


def run() -> None:
    log = bt.setup_logging(OUT_DIR, "INFO")
    df = bt.load_source_csv(ROOT / "keyword_search" / "out" / "results.csv", log)

    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer(bt.EMBEDDING_MODEL_NAME)

    results: dict[str, dict] = {}
    for concept in FLAGSHIP_CONCEPTS:
        meta_df = bt.get_concept_documents(df, concept)
        raw_docs = meta_df[bt.COLUMN_MAP["text"]].astype(str).tolist()
        cf_docs = [content_focused_text(d) for d in raw_docs]

        raw_words = sum(len(d.split()) for d in raw_docs)
        cf_words = sum(len(d.split()) for d in cf_docs)
        pct_stripped = round(100 * (raw_words - cf_words) / raw_words, 1) if raw_words else 0.0
        log.info(f"[{concept}] {len(raw_docs)} docs, stripped {pct_stripped}% of words before embedding")

        emb_path = CACHE_DIR / f"embeddings_content_focused_{concept}.npy"
        if emb_path.exists():
            embeddings = np.load(emb_path)
            log.info(f"[{concept}] Loaded cached content-focused embeddings.")
        else:
            embeddings = model.encode(
                cf_docs, batch_size=256, show_progress_bar=True,
                normalize_embeddings=True, convert_to_numpy=True,
            )
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            np.save(emb_path, embeddings)

        topic_model, topics = bt.fit_or_load_bertopic(
            concept, cf_docs, embeddings, CACHE_DIR, log, nr_topics=None, force=False,
        )
        n_real_topics = len(set(t for t in topics if t != -1))
        n_outliers = sum(1 for t in topics if t == -1)

        info = topic_model.get_topic_info()
        info = info[info["Topic"] != -1].sort_values("Count", ascending=False).head(8)
        top_topics = []
        for _, row in info.iterrows():
            terms = topic_model.get_topic(int(row["Topic"])) or []
            top_topics.append({
                "topic_id": int(row["Topic"]),
                "count": int(row["Count"]),
                "top_terms": [w for w, _ in terms[:5]],
            })

        results[concept] = {
            "n_docs": len(raw_docs),
            "words_stripped_pct": pct_stripped,
            "baseline_natural_topics_uncapped": BASELINE_NATURAL_TOPICS[concept],
            "content_focused_natural_topics_uncapped": n_real_topics,
            "content_focused_outlier_rate_pct": round(100 * n_outliers / len(raw_docs), 1),
            "top_topics_sample": top_topics,
        }
        log.info(f"[{concept}] baseline natural topics={BASELINE_NATURAL_TOPICS[concept]}, "
                 f"content-focused natural topics={n_real_topics}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / "content_context_comparison.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    log.info(f"Wrote comparison -> {out_path}")


if __name__ == "__main__":
    run()
