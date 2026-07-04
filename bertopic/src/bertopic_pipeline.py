# ─────────────────────────────────────────────────────────────────────────────
# IMPORTS
# ─────────────────────────────────────────────────────────────────────────────
import os
import sys
import json
import logging
import warnings
import importlib.util
from pathlib import Path
from collections import Counter
import traceback

import numpy as np
import pandas as pd
import pickle
import re

sys.path.append(str(Path(__file__).parent.parent.parent))

from bertopic import BERTopic
from umap import UMAP
from hdbscan import HDBSCAN
from sklearn.feature_extraction.text import CountVectorizer
from nltk.corpus import stopwords
from scipy.stats import entropy

from utils import log, load_keywords
from config import RESULT_PATH, TM_IN, TM_OUT as OUTPUT_DIR, TM_CACHE as CACHE_DIR
from viz_umap_2d import plot_concept_2d


KEYWORD_PATH     = TM_IN / "keywords.txt"
EMBEDDING_MODEL  = "all-MiniLM-L6-v2"

# Additional German stop words beyond NLTK defaults (abbreviations, artifacts)
EXTRA_STOP_WORDS = [
    "gv", "lt", "bzw", "std", "ca", "tf", "ak", "le",
    "sowie", "schlerinnen", "schler", "fr",
]

warnings.filterwarnings("ignore")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger(__name__)

log.info("Setup OK")


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def make_dirs_if_necessary(concept: str) -> None:
    """Create cache and output subdirectories for a concept if they don't exist."""
    (CACHE_DIR / concept).mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / concept).mkdir(parents=True, exist_ok=True)


# ─────────────────────────────────────────────────────────────────────────────
# STEP 1 — LOAD CSV
# ─────────────────────────────────────────────────────────────────────────────

def load_csv(csv_path: Path) -> pd.DataFrame:
    """
    Load the source CSV and coerce all columns to plain Python object dtype.

    Arrow-backed dtypes can cause downstream issues with BERTopic and
    sentence-transformers, so every column is explicitly cast to object.

    Args:
        csv_path: Path to the input CSV file.

    Returns:
        DataFrame with all columns as plain Python objects.
    """
    log.info(f"Loading CSV from {csv_path} …")
    df = pd.read_csv(csv_path, low_memory=False, dtype_backend="numpy_nullable")
    for col in df.columns:
        try:
            df[col] = df[col].astype(object)
        except Exception:
            pass
    log.info(f"  Rows: {len(df):,}  |  Columns: {df.shape[1]}")
    return df

# ─────────────────────────────────────────────────────────────────────────────
# STEP 2 — EMBEDDINGS (ALL DOCUMENTS)
# ─────────────────────────────────────────────────────────────────────────────

def get_embeddings_all(docs: list[str]) -> np.ndarray:
    """
    Compute or load sentence embeddings for the entire corpus.

    Embeddings are computed once and cached as a .npy file. On subsequent
    runs, the cache is loaded directly to avoid redundant computation.

    Args:
        docs: List of all text excerpts across all concepts.

    Returns:
        NumPy array of shape (n_docs, embedding_dim) with L2-normalised embeddings.
    """
    embed_path = CACHE_DIR / "embeddings_all.npy"

    if embed_path.exists():
        log.info("Loading embeddings from cache …")
        embeddings = np.load(embed_path)
        log.info(f"  Loaded embeddings: shape {embeddings.shape}")
        return embeddings

    log.info(f"No embeddings found at {embed_path}")
    try:
        from sentence_transformers import SentenceTransformer
        embedding_model = SentenceTransformer(EMBEDDING_MODEL)
        log.info(f"  Generating embeddings with '{EMBEDDING_MODEL}' …")
    except Exception as e:
        log.error(f"Error loading sentence transformer: {e}")
        raise

    embeddings = embedding_model.encode(
        docs,
        batch_size=256,
        show_progress_bar=True,
        normalize_embeddings=True,
        convert_to_numpy=True,
    )

    np.save(embed_path, embeddings)
    log.info(f"  Embeddings saved: shape {embeddings.shape}")
    return embeddings

# ─────────────────────────────────────────────────────────────────────────────
# STEP 3 — 2D UMAP PROJECTION (GLOBAL)
# ─────────────────────────────────────────────────────────────────────────────

def get_umap2d_all(embeddings: np.ndarray) -> np.ndarray:
    """
    Compute or load a 2D UMAP projection for the entire corpus.

    Fitting UMAP on all documents produces a global coordinate space where
    inter-concept relationships are visible. This projection is used for
    corpus-wide visualisations where all concepts are shown simultaneously.
    Results are cached once for the full run.

    Args:
        embeddings: Global embedding array of shape (n_all_docs, embedding_dim).

    Returns:
        NumPy array of shape (n_all_docs, 2) with 2D coordinates.
    """
    umap_cache = CACHE_DIR / "umap2d_all.npy"

    if umap_cache.exists():
        log.info("  Loading global 2D UMAP from cache …")
        coords = np.load(umap_cache)
        log.info(f"  Loaded coords: shape {coords.shape}")
        return coords

    log.info("  Computing global 2D UMAP projection …")
    reducer = UMAP(
        n_neighbors=20,
        n_components=2,
        min_dist=0.05,
        spread=1.2,
        metric="cosine",
        random_state=42,
        low_memory=False,
        verbose=True,
    )
    coords = reducer.fit_transform(embeddings)
    np.save(umap_cache, coords)
    log.info(f"  Global 2D UMAP saved: shape {coords.shape}")
    return coords

# ─────────────────────────────────────────────────────────────────────────────
# STEP 4 — GET DOCUMENTS
# ─────────────────────────────────────────────────────────────────────────────

def get_documents(df: pd.DataFrame, keyword: str) -> tuple[list[str], pd.DataFrame]:
    """
    Filter the full dataframe to rows matching a keyword and persist them.

    The global DataFrame index is preserved as 'doc_id' so that concept-level
    document rows can later be mapped back to the global embedding array.

    Args:
        df:      Full source DataFrame containing all concepts.
        keyword: The concept/search term to filter by.

    Returns:
        texts:   List of raw text excerpts for the concept.
        docs_df: Filtered DataFrame with a 'doc_id' column added.
    """
    docs_dir = OUTPUT_DIR / keyword / f"documents_{keyword}.csv"

    docs_df: pd.DataFrame = df.loc[
        df["search_term"] == keyword,
        ["text_excerpt", "search_term", "match_term", "state", "school type", "grade", "year", "subject"],
    ]
    texts = list(docs_df["text_excerpt"])

    # Preserve global index as an explicit column for embedding lookup
    docs_df["doc_id"] = docs_df.index
    docs_df.to_csv(docs_dir)

    log.info(f"  {len(docs_df)} documents saved for concept '{keyword}'.")
    return texts, docs_df


# ─────────────────────────────────────────────────────────────────────────────
# STEP 5 — EMBEDDINGS (CONCEPT SLICE)
# ─────────────────────────────────────────────────────────────────────────────

def get_embeddings(embeddings_all: np.ndarray, meta_df: pd.DataFrame) -> np.ndarray:
    """
    Slice the global embedding array to rows belonging to a single concept.

    Uses 'doc_id' (which equals the original DataFrame index) as positional
    indices into the global embedding array, so the slice is always aligned
    with the concept's document list.

    Args:
        embeddings_all: Global embedding array of shape (n_all_docs, embedding_dim).
        meta_df:        Concept-level DataFrame containing a 'doc_id' column.

    Returns:
        NumPy array of shape (n_concept_docs, embedding_dim).
    """
    return embeddings_all[meta_df["doc_id"].to_numpy()]


# ─────────────────────────────────────────────────────────────────────────────
# STEP 6 — BERTOPIC
# ─────────────────────────────────────────────────────────────────────────────

def run_bertopic(
    meta_df:    pd.DataFrame,
    docs:       list[str],
    embeddings: np.ndarray,
    keyword:    str,
) -> tuple[BERTopic, list[int], np.ndarray]:
    """
    Fit a BERTopic model for a single concept, or load it from cache.

    Hyperparameters are adapted to corpus size: small corpora (<200 docs)
    use relaxed min_df/max_df and smaller cluster sizes to avoid empty
    vocabularies. A fallback vectorizer with no constraints is used if the
    primary vectorizer raises a ValueError (e.g. max_df < min_df).

    The fitted model, topic assignments and probabilities are cached as a
    pickle so that reruns skip inference entirely.

    Args:
        meta_df:    Concept-level DataFrame (used to attach topic assignments).
        docs:       List of text excerpts for the concept.
        embeddings: Concept-level embedding array, aligned with `docs`.
        keyword:    Concept name, used for cache/output paths.

    Returns:
        topic_model: Fitted BERTopic instance.
        topics:      List of integer topic IDs, one per document (-1 = outlier).
        probs:       Topic probability array (empty when calculate_probabilities=False).
    """
    topic_cache = CACHE_DIR / keyword / f"topic_model_{keyword}.pkl"
    docs_dir    = OUTPUT_DIR / keyword / f"documents_{keyword}.csv"

    # ── Load from cache if available ─────────────────────────────────────────
    if topic_cache.exists():
        log.info("  Loading BERTopic model from cache …")
        with open(topic_cache, "rb") as f:
            cached = pickle.load(f)
        topic_model, topics, probs = cached["model"], cached["topics"], cached["probs"]

        meta_df["bertopic_topic"] = topics
        meta_df.to_csv(docs_dir)
        return topic_model, topics, probs

    # ── Adapt hyperparameters to corpus size ──────────────────────────────────
    log.info("  Running BERTopic …")
    log.info(f"    Embeddings: {embeddings.shape}  |  Docs: {len(docs)}")

    if len(docs) < 200:
        min_df, max_df, min_cluster_size = 1, 1.0, 10
    else:
        min_df, max_df, min_cluster_size = 3, 0.8, 15

    umap_model = UMAP(
        n_neighbors=15,
        n_components=5,
        min_dist=0.0,
        metric="cosine",
        random_state=42,
        low_memory=False,
    )
    hdbscan_model = HDBSCAN(
        min_cluster_size=min_cluster_size,
        min_samples=5,
        metric="euclidean",
        cluster_selection_method="eom",
        prediction_data=True,
    )
    german_stop_words = stopwords.words("german") + EXTRA_STOP_WORDS

    # ── Primary fit (with vocabulary constraints) ─────────────────────────────
    try:
        vectorizer = CountVectorizer(
            stop_words=german_stop_words,
            min_df=min_df,
            max_df=max_df,
            ngram_range=(1, 2),
            token_pattern=r"(?u)\b[a-zA-ZäöüÄÖÜß\w]{3,}\b", # minimum length of 3 letters including umlaute => fails to preserve umlaute because CountVectorizer strips them beforehand
        )
        topic_model = BERTopic(
            umap_model=umap_model,
            hdbscan_model=hdbscan_model,
            vectorizer_model=vectorizer,
            top_n_words=20,
            verbose=True,
            calculate_probabilities=False,
            nr_topics=11,
        )
        topics, probs = topic_model.fit_transform(docs, embeddings)

    # ── Fallback: unconstrained vectorizer ────────────────────────────────────
    except Exception as e:

        log.warning(f"  Primary vectorizer failed ({e}), retrying without constraints …")
        
        vectorizer = CountVectorizer(
            stop_words=german_stop_words,
            ngram_range=(1, 2),
        )
        topic_model = BERTopic(
            umap_model=umap_model,
            hdbscan_model=hdbscan_model,
            vectorizer_model=vectorizer,
            top_n_words=20,
            verbose=True,
            calculate_probabilities=False,
            nr_topics=11,
        )
        topics, probs = topic_model.fit_transform(docs, embeddings)

    log.info(f"  Topics found: {len(set(topics))}")

    # ── Persist model and updated document metadata ───────────────────────────
    with open(topic_cache, "wb") as f:
        pickle.dump({"keyword": keyword, "model": topic_model, "topics": topics, "probs": probs}, f)

    meta_df["bertopic_topic"] = topics
    meta_df.to_csv(docs_dir)

    return topic_model, topics, probs


# ─────────────────────────────────────────────────────────────────────────────
# STEP 7 — 2D UMAP PROJECTION (CONCEPT-LOCAL)
# ─────────────────────────────────────────────────────────────────────────────

def get_umap2d(embeddings: np.ndarray, keyword: str) -> np.ndarray:
    """
    Compute or load a 2D UMAP projection for a single concept's embeddings.

    The projection is fitted only on the concept-local embedding subset,
    so the resulting manifold reflects within-concept variance rather than
    between-concept structure. Results are cached per concept.

    Args:
        embeddings: Concept-level embedding array of shape (n_docs, embedding_dim).
        keyword:    Concept name, used for cache path.

    Returns:
        NumPy array of shape (n_docs, 2) with 2D coordinates.
    """
    umap_cache = CACHE_DIR / keyword / f"umap2d_{keyword}.npy"

    if umap_cache.exists():
        log.info("  Loading 2D UMAP from cache …")
        coords = np.load(umap_cache)
        log.info(f"  Loaded coords: shape {coords.shape}")
        return coords

    log.info("  Computing 2D UMAP projection …")
    reducer = UMAP(
        n_neighbors=20,
        n_components=2,
        min_dist=0.05,
        spread=1.2,
        metric="cosine",
        random_state=42,
        low_memory=False,
        verbose=True,
    )
    coords = reducer.fit_transform(embeddings)
    np.save(umap_cache, coords)
    log.info(f"  2D UMAP saved: shape {coords.shape}")
    return coords


# ─────────────────────────────────────────────────────────────────────────────
# STEP 8 — TOPIC–SUBJECT DISTRIBUTION ANALYSIS
# ─────────────────────────────────────────────────────────────────────────────

def analyze_topic_subject_distribution(
    df:          pd.DataFrame,
    topic_model: BERTopic,
    keyword:     str,
) -> None:
    """
    Compute and save topic–subject cross-distributions and a term summary.

    Produces five output files in OUTPUT_DIR / keyword:
      1. topic_info_{keyword}.csv               — per-topic counts, proportions, top terms
      2. dist_topics_over_subjects_{keyword}.csv — normalised topic rows over subject columns
      3. dist_subjects_over_topics_{keyword}.csv — normalised subject rows over topic columns
      4. topic_subject_summary_{keyword}.txt     — human-readable top-N topics per subject
      5. topic_terms_{keyword}.csv              — top terms and scores for every topic

    Both distribution CSVs include Shannon entropy (base 2) per row, absolute
    row totals, and a TOTAL summary row with marginal distributions.

    Args:
        df:          Concept-level DataFrame with 'subject' and 'bertopic_topic' columns.
        topic_model: Fitted BERTopic instance for the concept.
        keyword:     Concept name, used for output paths and filenames.
    """
    keyword_out_dir = OUTPUT_DIR / keyword
    keyword_out_dir.mkdir(parents=True, exist_ok=True)

    # ── Topic metadata ────────────────────────────────────────────────────────
    topic_info = topic_model.get_topic_info()
    sum_docs   = topic_info["Count"].sum()

    topic_info["Proportion"] = topic_info["Count"] / sum_docs
    topic_info = topic_info[["Topic", "Count", "Proportion", "Name", "Representation", "Representative_Docs"]]

    filename_topic_info = f"topic_info_{keyword}.csv"
    topic_info.to_csv(keyword_out_dir / filename_topic_info, index=False)
    log.info(f"  Saved: {filename_topic_info}")

    # ── Build working dataframe ───────────────────────────────────────────────
    work = df[["subject", "bertopic_topic"]].copy()
    id_to_name       = dict(zip(topic_info["Topic"], topic_info["Name"]))
    work["topic_name"] = work["bertopic_topic"].map(id_to_name)

    # ── 1) Topics over subjects (rows=topics, cols=subjects) ──────────────────
    topics_over_subjects = (
        work.groupby(["topic_name", "subject"])
        .size()
        .unstack(fill_value=0)
    )
    counts = topics_over_subjects.copy()

    # Normalise each topic row to a probability distribution over subjects
    topics_over_subjects = topics_over_subjects.div(counts.sum(axis=1), axis=0)
    topics_over_subjects["entropy"]           = topics_over_subjects.apply(lambda row: entropy(row, base=2), axis=1)
    topics_over_subjects["topic_total"]       = counts.sum(axis=1)
    topics_over_subjects["topic_proportion"]  = topics_over_subjects["topic_total"] / sum_docs

    # Marginal TOTAL row: distribution of all docs across subjects
    subject_totals                  = counts.sum(axis=0)
    total_row_1                     = (subject_totals / subject_totals.sum()).to_dict()
    total_row_1["entropy"]          = entropy(list(subject_totals / subject_totals.sum()), base=2)
    total_row_1["topic_total"]      = int(subject_totals.sum())
    total_row_1["topic_proportion"] = 1.0
    topics_over_subjects.loc["Total"] = total_row_1

    topics_over_subjects = topics_over_subjects.round(4)
    filename_1 = f"dist_topics_over_subjects_{keyword}.csv"
    topics_over_subjects.to_csv(keyword_out_dir / filename_1)
    log.info(f"  Saved: {filename_1}")

    # ── 2) Subjects over topics (rows=subjects, cols=topics) ──────────────────
    subjects_over_topics_counts = counts.T

    # Normalise each subject row to a probability distribution over topics
    subjects_over_topics = subjects_over_topics_counts.div(
        subjects_over_topics_counts.sum(axis=1), axis=0
    )
    subjects_over_topics["entropy"]            = subjects_over_topics.apply(lambda row: entropy(row, base=2), axis=1)
    subjects_over_topics["subject_total"]      = subjects_over_topics_counts.sum(axis=1)
    subjects_over_topics["subject_proportion"] = subjects_over_topics["subject_total"] / sum_docs

    # Marginal TOTAL row: distribution of all docs across topics
    topic_totals                       = subjects_over_topics_counts.sum(axis=0)
    total_row_2                        = (topic_totals / topic_totals.sum()).to_dict()
    total_row_2["entropy"]             = entropy(list(topic_totals / topic_totals.sum()), base=2)
    total_row_2["subject_total"]       = int(topic_totals.sum())
    total_row_2["subject_proportion"]  = 1.0
    subjects_over_topics.loc["Total"]  = total_row_2

    subjects_over_topics = subjects_over_topics.round(4)
    filename_2 = f"dist_subjects_over_topics_{keyword}.csv"
    subjects_over_topics.to_csv(keyword_out_dir / filename_2)
    log.info(f"  Saved: {filename_2}")

    # ── 3) Human-readable summary: all topics per subject ─────────────────────
    lines = []
    for subject, group in work.groupby("subject"):
        n            = len(group)
        topic_counts = Counter(group["topic_name"]).most_common()

        lines.append(f"{subject} (n={n})")
        lines.append(f"{'count':<8} | topic name")
        lines.append("-" * 50)
        for topic_name, count in topic_counts:
            lines.append(f"{count:<8} | {topic_name}")
        lines.append("")

    filename_3   = f"topic_subject_summary_{keyword}.txt"
    summary_path = keyword_out_dir / filename_3
    with open(summary_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    log.info(f"  Saved: {filename_3}")

    # ── 4) Top terms per topic ────────────────────────────────────────────────
    terms_df = pd.DataFrame()
    for i in sorted(set(topic_model.topics_)):
        topic_terms = topic_model.get_topic(topic=i)
        if topic_terms:
            terms_df[f"Topic {i} terms"]         = [t[0] for t in topic_terms]
            terms_df[f"Topic {i} probabilities"] = [t[1] for t in topic_terms]

    terms_df = terms_df.round(4)
    filename_4 = f"topic_terms_{keyword}.csv"
    terms_df.to_csv(OUTPUT_DIR / keyword / filename_4)
    log.info(f"  Saved: {filename_4}")

    log.info(f"  All outputs → {keyword_out_dir}")


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    """
    Run the full BERTopic pipeline for all concepts.
    Pipeline steps:
      1. Load CSV and keywords
      2. Compute global embeddings (once, shared across concepts)
      3. Compute global 2D UMAP for corpus-wide visualisation (once)
    Per concept:
      4. Get documents for concept
      5. Slice concept-level embeddings from global array
      6. Fit BERTopic model
      7. Compute concept-local 2D UMAP for visualisation
      8. Analyse topic–subject distributions
      9. Plot 2D UMAP coloured by topic and by subject (local and global)
    """
    log.info("=" * 70)
    log.info("  German Curriculum BERTopic Analysis Pipeline")
    log.info("=" * 70)

    if not RESULT_PATH.exists():
        log.error(f"Required file not found: {RESULT_PATH}")
        sys.exit(1)

    # Step 1 — Load CSV and keywords
    keywords = load_keywords(KEYWORD_PATH)
    df       = load_csv(RESULT_PATH)

    # Step 2 — Global embeddings (computed once for all concepts)
    embeddings_all = get_embeddings_all(list(df["text_excerpt"]))

    # Step 3 — Global 2D UMAP (computed once for all concepts)
    umap_2d_all = get_umap2d_all(embeddings_all)

    for keyword in keywords:
        log.info("=" * 70)
        log.info(f"  CONCEPT: {keyword}")
        log.info("=" * 70)
        try:
            make_dirs_if_necessary(keyword)

            # Step 4 — Documents for this concept
            keyword_docs, keyword_df = get_documents(df, keyword)

            # Step 5 — Concept-level embeddings (slice from global array)
            embeddings = get_embeddings(embeddings_all, keyword_df)

            # Step 6 — BERTopic
            topic_model, topics, probs = run_bertopic(keyword_df, keyword_docs, embeddings, keyword)

            # Step 7 — Concept-local 2D UMAP
            coords = get_umap2d(embeddings, keyword)

            # Step 8 — Topic–subject distribution analysis
            analyze_topic_subject_distribution(keyword_df, topic_model, keyword)

            # Step 9 — Visualisations (local and global embedding space)
            for var in ["topic", "subject"]:

                # local embedding space, load umap embeddings from cache
                plot_concept_2d(umap_embeddings=None, concept=keyword, color_by=var)
                
                # global embedding space
                plot_concept_2d(umap_embeddings=umap_2d_all, concept=keyword, color_by=var)

        except Exception:
            log.error(f"Pipeline failed for concept '{keyword}'")
            log.error(traceback.format_exc())


if __name__ == "__main__":
    main()
