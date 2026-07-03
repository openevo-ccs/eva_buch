
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


KEYWORD_PATH = TM_IN / "keywords.txt"
EMBEDDING_MODEL = "all-MiniLM-L6-v2"

warnings.filterwarnings("ignore")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger(__name__)

log.info("Setup OK")


def make_dirs_if_necessary(concept):
    keyword_dir = CACHE_DIR / concept
    keyword_dir.mkdir(parents=True, exist_ok=True)
    keyword_out_dir = OUTPUT_DIR / concept
    keyword_out_dir.mkdir(parents=True, exist_ok=True)

# ─────────────────────────────────────────────────────────────────────────────
# 2.  LOAD CSV  (force Python-native dtypes to avoid Arrow backend issues)
# ─────────────────────────────────────────────────────────────────────────────

def load_csv(csv_path: Path) -> pd.DataFrame:
    log.info(f"Loading CSV from {csv_path} …")
    df = pd.read_csv(csv_path, low_memory=False, dtype_backend="numpy_nullable")
    # Convert every column to plain Python objects so Arrow never appears
    for col in df.columns:
        try:
            df[col] = df[col].astype(object)
        except Exception:
            pass
    
    log.info(f"  Rows: {len(df):,}  |  Columns: {df.shape[1]}")
    return df


# def get_excerpts(df: pd.DataFrame, keyword: str | None, docs_cache: Path):
#     """
#     Extract text excerpt belonging to a specific key word.
#     Assumes the keyword column is named 'search_term' - adjust as needed.
#     """
   
#    # excerpts = list(df.loc[df["search_term"] == keyword, ["text_excerpt","subject"]])
#     if keyword:
#         excerpts = df.loc[df["search_term"] == keyword, ["text_excerpt", "state","school type","grade","year","subject"]]
#     else:
#         excerpts = df[["text_excerpt", "state","school type","grade","year","subject"]]
    
#     print(excerpts, len(excerpts), type(excerpts))
#     if len(excerpts) > 0:
#         print(f"{len(excerpts)} excerpts")
#         excerpts.to_csv(docs_cache)
        
#     else:
#         print("Keyword does not exist")
#     return excerpts


def get_documents(df: pd.DataFrame, keyword: str) -> tuple[list[str], pd.DataFrame]:
    docs_dir = OUTPUT_DIR / keyword / f"documents_{keyword}.csv"
    # try:
    #     docs = pd.read_csv(docs_cache)
    #     log.info(f"  Loaded {len(docs):,} cached documents.")
    # except Exception as e:
    #     log.error(f"Failed to load docs from {docs_cache}: {e}")

    docs_df = df.loc[df["search_term"] == keyword, ["text_excerpt", "search_term", "match_term","state","school type","grade","year","subject"]]
    texts = list(docs_df["text_excerpt"])
    docs_df['doc_id'] = docs_df.index
    docs_df.to_csv(docs_dir)

    log.info(f"{len(docs_df)} documents saved for concept {keyword}.")
    
    return texts, docs_df


# ─────────────────────────────────────────────────────────────────────────────
# 4.  ALL EMBEDDINGS
# ─────────────────────────────────────────────────────────────────────────────


def get_embeddings_all(docs: list[str]) -> np.ndarray:

    embed_path = CACHE_DIR / "embeddings_all.npy"
    if embed_path.exists():
        log.info("Loading embeddings from cache …")
        embeddings = np.load(embed_path)
        log.info(f"  Loaded embeddings: shape {embeddings.shape}")
        return embeddings

    log.info(f"No embeddings found at {embed_path}")
    try:
        from sentence_transformers import SentenceTransformer
        emedding_model = SentenceTransformer(EMBEDDING_MODEL)
        log.info(f"Generating embeddings with {EMBEDDING_MODEL} …")
    except Exception as e:
        log.error(f"Error loading sentence transformer: {e}")
    
    
    
    

    
    embeddings =  emedding_model.encode(
        docs, 
        batch_size=256,
        show_progress_bar=True,
        normalize_embeddings=True,
        convert_to_numpy=True,
    )

    np.save(embed_path, embeddings)
    log.info(f"  Embeddings saved: shape {embeddings.shape}")

    return embeddings
 


def get_embeddings(embeddings_all: np.ndarray, meta_df: pd.DataFrame):
    return embeddings_all[meta_df["doc_id"]]

def run_bertopic(
    meta_df: pd.DataFrame,
    docs:       list[str],
    embeddings: np.ndarray,
    keyword:      str,
    ) -> tuple:
    topic_cache = CACHE_DIR / keyword / f"topic_model_{keyword}.pkl"
    #meta_path = CACHE_DIR / keyword / f"documents_{keyword}.csv"
    docs_dir = OUTPUT_DIR / keyword / f"documents_{keyword}.csv"
    

    if topic_cache.exists():
        log.info("Loading BERTopic model from cache …")
        with open(topic_cache, "rb") as f:
            cached = pickle.load(f)
            topic_model, topics, probs = (cached["model"], cached["topics"], cached["probs"])
            
            meta_df["bertopic_topic"] = topics
            meta_df.to_csv(docs_dir)
            
            return topic_model, topics, probs
   
    log.info("Running Guided BERTopic …")
    log.info(f"Length embeddings: {len(embeddings)}")
    log.info(f"Length docs: {len(docs)}")

    if len(docs) < 200:
        min_df, max_df, min_cluster_size = 1, 1, 10
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
    german_stop_words = stopwords.words('german') + ["gv", "lt", "bzw", "std", "ca", "tf", "ak", "le", "sowie", "schlerinnen","schler","fr"]
    
    
    try:
        vectorizer = CountVectorizer(
            stop_words=german_stop_words,
            min_df=min_df,
            max_df=max_df,
            ngram_range=(1, 2),
            token_pattern=r"(?u)\b[a-zA-ZäöüÄÖÜß\w]{3,}\b",
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
    except Exception as e:
        log.error(e)
        vectorizer = CountVectorizer(
            stop_words=german_stop_words,
            ngram_range=(1, 2)
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



    with open(topic_cache, "wb") as f:
        pickle.dump({
            "keyword":       keyword,
            "model":         topic_model,
            "topics":        topics,
            "probs":         probs,
        }, f)
    meta_df["bertopic_topic"] = topics
    # topic_df = pd.DataFrame({
    #     "global_doc_id" : meta_df.index,
    #     "bertopic_topic": topics
    # })
    meta_df.to_csv(docs_dir)

    return topic_model, topics, probs




# ─────────────────────────────────────────────────────────────────────────────
# 7.  3-D UMAP PROJECTION
# ─────────────────────────────────────────────────────────────────────────────

def get_umap2d(embeddings: np.ndarray, keyword: str) -> np.ndarray:
    umap_cache = CACHE_DIR / keyword / f"umap2d_{keyword}.npy"
    if umap_cache.exists():
        log.info("Loading 2-D UMAP from cache …")
        coords = np.load(umap_cache)
        log.info(f"  Loaded coords: shape {coords.shape}")
        return coords

    log.info("Computing 2-D UMAP projection …")
    try:
        from umap import UMAP
    except ImportError:
        log.error("umap-learn not installed.")
        sys.exit(1)

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
    log.info(f"  2-D UMAP saved: shape {coords.shape}")
    return coords

def get_umap2d_all(embeddings: np.ndarray) -> np.ndarray:
    umap_cache = CACHE_DIR / "umap2d_all.npy"
    if umap_cache.exists():
        log.info("Loading 2-D UMAP from cache …")
        coords = np.load(umap_cache)
        log.info(f"  Loaded coords: shape {coords.shape}")
        return coords

    log.info("Computing 2-D UMAP projection …")
    try:
        from umap import UMAP
    except ImportError:
        log.error("umap-learn not installed.")
        sys.exit(1)

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
    log.info(f"  2-D UMAP saved: shape {coords.shape}")
    return coords

    


def analyze_topic_subject_distribution(df, topic_model, keyword):
    keyword_out_dir = OUTPUT_DIR / keyword
    keyword_out_dir.mkdir(parents=True, exist_ok=True)
    """
    Analyze distribution of topics over subjects and vice versa.
    
    Args:
        topics:      list of topic IDs from BERTopic (same length as df)
        df:          DataFrame with a 'subject' column
        topic_model: fitted BERTopic model (to get topic labels)
        output_dir:  where to save the output files
    """
    topic_info = topic_model.get_topic_info()
    sum_docs = topic_info["Count"].sum()
    print(sum_docs, len(df))
    topic_info["Proportion"] = topic_info["Count"]/sum_docs 
    topic_info = topic_info[["Topic","Count","Proportion","Name","Representation","Representative_Docs"]]
    
    filename_topic_info = f"topic_info_{keyword}.csv"
    topic_info.to_csv(keyword_out_dir / filename_topic_info, index=False)

    # --- Build a working dataframe ---
    tdf_path = OUTPUT_DIR / keyword / f"documents_{keyword}.csv"
    tdf = pd.read_csv(tdf_path)
    log.info(f"Document df of length {len(tdf)}")

    work = df[["subject", "bertopic_topic"]].copy()


    id_to_name = dict(zip(topic_info["Topic"], topic_info["Name"]))
    work["topic_name"] = work["bertopic_topic"].map(id_to_name)

    # Drop outlier topic (-1) if desired — comment out to keep it
    #work = work[work["topic_id"] != -1]

    

    # ----------------------------------------------------------------
    # 1) Topics over subject areas  →  rows=topics, cols=subject areas
    # ----------------------------------------------------------------
    topics_over_subjects = (
        work.groupby(["topic_name", "subject"])
        .size()
        .unstack(fill_value=0)
    )
    counts = topics_over_subjects.copy()
    topics_over_subjects = topics_over_subjects.div(counts.sum(axis=1), axis=0)
    topics_over_subjects["entropy"] = topics_over_subjects.apply(
        lambda row: entropy(row, base=2), axis=1
    )
    topics_over_subjects["topic_total"] = counts.sum(axis=1)
    topics_over_subjects["topic_proportion"] = topics_over_subjects["topic_total"] / sum_docs

    # total row: distribution across subject areas + totals
    subject_totals = counts.sum(axis=0)
    total_row_1 = (subject_totals / subject_totals.sum()).to_dict()
    total_row_1["entropy"]           = entropy(list(subject_totals / subject_totals.sum()), base=2)
    total_row_1["topic_total"]       = int(subject_totals.sum())
    total_row_1["topic_proportion"]  = 1.0
    topics_over_subjects.loc["TOTAL"] = total_row_1

    topics_over_subjects = topics_over_subjects.round(4)
    filename_1 = f"dist_topics_over_subjects_{keyword}.csv"
    topics_over_subjects.to_csv(keyword_out_dir / filename_1)

    # ----------------------------------------------------------------
    # 2) subjects over topics  →  rows=subjects, cols=topics
    # ----------------------------------------------------------------
    subjects_over_topics_counts = counts.T
    subjects_over_topics = subjects_over_topics_counts.div(
        subjects_over_topics_counts.sum(axis=1), axis=0
    )
    subjects_over_topics["entropy"] = subjects_over_topics.apply(
        lambda row: entropy(row, base=2), axis=1
    )
    subjects_over_topics["subject_total"]      = subjects_over_topics_counts.sum(axis=1)
    subjects_over_topics["subject_proportion"] = subjects_over_topics["subject_total"] / sum_docs

    # total row: distribution across topics + totals
    topic_totals = subjects_over_topics_counts.sum(axis=0)
    total_row_2 = (topic_totals / topic_totals.sum()).to_dict()
    total_row_2["entropy"]             = entropy(list(topic_totals / topic_totals.sum()), base=2)
    total_row_2["subject_total"]       = int(topic_totals.sum())
    total_row_2["subject_proportion"]  = 1.0
    subjects_over_topics.loc["TOTAL"]  = total_row_2

    subjects_over_topics = subjects_over_topics.round(4)
    filename_2 = f"dist_subjects_over_topics_{keyword}.csv"
    subjects_over_topics.to_csv(keyword_out_dir / filename_2)
    
    # ----------------------------------------------------------------
    # 3) Human-readable summary: top 5 topics per subject
    # ----------------------------------------------------------------
    lines = []
    for subject, group in work.groupby("subject"):
        n = len(group)
        topic_counts = Counter(group["topic_name"]).most_common()

        lines.append(f"{subject} (n={n})")
        lines.append(f"{'count':<8} | topic name")
        lines.append("-" * 50)
        for topic_name, count in topic_counts:
            lines.append(f"{count:<8} | {topic_name}")
        lines.append("")  

    filename_3 = f"topic_subject_summary_{keyword}.txt"
    summary_path = keyword_out_dir / filename_3
    with open(summary_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    df = pd.DataFrame()
    topics = sorted(set(topic_model.topics_))
    
    for i in topics:
        
        topic_terms = topic_model.get_topic(topic=i)
        if topic_terms:
            terms = [t[0] for t in topic_terms]
            values = [t[1] for t in topic_terms]
            df[f"Topic {i} terms"] = terms
            df[f"Topic {i} probabilities"] = values
    df = df.round(4)
    filename_4 = f"topic_terms_{keyword}.csv"
    df.to_csv(OUTPUT_DIR / keyword / filename_4)

    print(f"Saved:\n  {filename_topic_info}\n  {filename_1}\n  {filename_2}\n  {filename_3}\n  {filename_4}")
    print(f"  → {keyword_out_dir}")
    




# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main():
    log.info("=" * 70)
    log.info("  German Curriculum BERTopic Analysis Pipeline")
    log.info("=" * 70)

    for p in [RESULT_PATH]:
        if not p.exists():
            log.error(f"Required file not found: {p}")
            sys.exit(1)
    # 1. Keywords
    keywords = load_keywords(KEYWORD_PATH)
    # 2. CSV
    df = load_csv(RESULT_PATH)
    # 3. All embeddings
    embeddings_all = get_embeddings_all(list(df["text_excerpt"]))

    umap_2d_all = get_umap2d_all(embeddings_all)


    for keyword in keywords:
        # if keyword != "Konkurrenz":
        #     continue
        log.info("=" * 70)
        log.info(f"  Concept {keyword}")
        log.info("=" * 70)
        try:

            
            make_dirs_if_necessary(keyword)

            # 4. Documents
            keyword_docs, keyword_df = get_documents(df, keyword)
            # 5. Concept embeddings
            embeddings = get_embeddings(embeddings_all, keyword_df)
            
            # 6. BERTopic
            topic_model, topics, probs = run_bertopic(keyword_df, keyword_docs, embeddings, keyword)
        
            # 7. Local 2D UMAP
            coords = get_umap2d(embeddings, keyword)

            # 8. Diagnostics
            analyze_topic_subject_distribution(keyword_df, topic_model, keyword)

            # 9. Plot
            for var in ["topic", "subject"]:
                # local
                plot_concept_2d(umap_embeddings=None, concept=keyword, color_by=var)
                # global
                plot_concept_2d(umap_embeddings=umap_2d_all, concept=keyword, color_by=var)

        except Exception as e:
            
            log.error(f"An error occurred on keyword {keyword}")
            log.error(traceback.format_exc())
            


if __name__ == "__main__":
    main()