# ─────────────────────────────────────────────────────────────────────────────
# IMPORTS
# ─────────────────────────────────────────────────────────────────────────────
import pandas as pd
import re
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.decomposition import LatentDirichletAllocation
import pyLDAvis
import pyLDAvis.lda_model
import spacy
import os
import numpy as np
import pickle
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent.parent))
from config import RESULT_PATH as DATA_PATH, LDA_IN, LDA_OUT as OUT_DIR

print("All libraries successfully imported!")

# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────────────────────────────────────
KEYWORD_PATH         = LDA_IN / "keywords_topic_modelling.txt"
EXCLUDE_TERMS_PATH   = LDA_IN / "exclude_list.txt"

# spaCy model for German lemmatisation and stopword removal
SPACY_MODEL = "de_core_news_sm"

# Topic counts to run for each concept (one model is fitted per value)
N_TOPICS_LIST = [5, 7, 10]


# ─────────────────────────────────────────────────────────────────────────────
# STEP 1 — LOAD DATA
# ─────────────────────────────────────────────────────────────────────────────

def load_data(file_path: Path) -> pd.DataFrame:
    """
    Load the keyword search results from a CSV file.

    Args:
        file_path: Path to the CSV produced by the keyword search pipeline.

    Returns:
        DataFrame with all search results.
    """
    return pd.read_csv(file_path)


def load_keywords(keyword_path: Path) -> list[str]:
    """
    Load the list of concepts to model from a plain-text file.

    Each line should contain one concept label. Blank lines and surrounding
    whitespace are stripped.

    Args:
        keyword_path: Path to the keyword list file.

    Returns:
        List of concept label strings.
    """
    with open(keyword_path, "r") as f:
        return [line.strip() for line in f if line.strip()]


# ─────────────────────────────────────────────────────────────────────────────
# STEP 2 — GET EXCERPTS
# ─────────────────────────────────────────────────────────────────────────────

def get_excerpts(df: pd.DataFrame, keyword: str | None = None) -> list[dict] | bool:
    """
    Filter search results to excerpts belonging to a specific concept.

    Args:
        df:      Full results DataFrame with at least 'search_term' and
                 'text_excerpt' columns.
        keyword: Concept label to filter by. If None, all rows are returned.

    Returns:
        List of dicts (one per document) containing text_excerpt and metadata,
        or False if no matching excerpts are found.
    """
    cols = ["text_excerpt", "state", "school type", "grade", "year", "subject"]

    if keyword:
        excerpts = df.loc[df["search_term"] == keyword, cols].to_dict("records")
    else:
        excerpts = df[cols].to_dict("records")

    if not excerpts:
        print(f"  No excerpts found for keyword '{keyword}'")
        return False

    print(f"  {len(excerpts)} excerpts for '{keyword}'")
    return excerpts


# ─────────────────────────────────────────────────────────────────────────────
# STEP 3 — PREPROCESSING
# ─────────────────────────────────────────────────────────────────────────────

def preprocess_text(excerpts: list[dict]) -> list[str]:
    """
    Preprocess raw text excerpts for LDA: clean, lemmatise, and remove stopwords.

    Processing steps per excerpt:
      - Strip non-alphabetic characters (German umlauts retained)
      - Lemmatise using spaCy's German model
      - Lowercase all tokens
      - Remove spaCy stopwords, project-specific exclude-list terms,
        and tokens shorter than 3 characters

    The exclude list is loaded from EXCLUDE_TERMS_PATH (comma-separated).

    Args:
        excerpts: List of dicts as returned by get_excerpts(), each containing
                  at least a 'text_excerpt' key.

    Returns:
        List of preprocessed strings (one per excerpt), with empty string for
        non-string inputs.
    """
    nlp        = spacy.load(SPACY_MODEL)
    stop_words = nlp.Defaults.stop_words

    with open(EXCLUDE_TERMS_PATH, "r") as f:
        exclude_terms = set(f.read().split(", "))
    print(f"  {len(exclude_terms)} terms in exclude list")

    processed_texts = []
    for item in excerpts:
        text = item["text_excerpt"]
        if not isinstance(text, str):
            processed_texts.append("")
            continue

        # Remove characters outside the expected German/Latin alphabet
        text = re.sub(r"[^a-zA-ZäöüÄÖÜßéèêëçñ\s]", "", text)

        doc    = nlp(text)
        tokens = [
            token.lemma_.lower()
            for token in doc
            if token.text.lower() not in stop_words
            and token.lemma_.lower() not in exclude_terms
            and token.text.lower() not in exclude_terms
            and len(token.text) > 2
        ]
        processed_texts.append(" ".join(tokens))

    return processed_texts


# ─────────────────────────────────────────────────────────────────────────────
# STEP 4 — DOCUMENT-TERM MATRIX
# ─────────────────────────────────────────────────────────────────────────────

def create_dtm(
    processed_texts: list[str],
    max_features:    int   = 5000,
    min_df:          int   = 5,
    max_df:          float = 0.8,
) -> tuple[object, CountVectorizer]:
    """
    Build a document-term matrix from preprocessed text.

    Args:
        processed_texts: List of preprocessed, space-tokenised strings.
        max_features:    Maximum vocabulary size (most frequent terms kept).
        min_df:          Minimum document frequency for a term to be included.
        max_df:          Maximum document frequency (as a proportion) above
                         which a term is treated as too common and excluded.

    Returns:
        dtm:        Sparse document-term count matrix (n_docs × n_terms).
        vectorizer: Fitted CountVectorizer (needed for term names and pyLDAvis).
    """
    vectorizer = CountVectorizer(
        max_features=max_features,
        min_df=min_df,
        max_df=max_df,
    )
    dtm = vectorizer.fit_transform(processed_texts)
    return dtm, vectorizer


# ─────────────────────────────────────────────────────────────────────────────
# STEP 5 — TRAIN LDA
# ─────────────────────────────────────────────────────────────────────────────

def train_lda(
    dtm:          object,
    n_topics:     int = 10,
    random_state: int = 42, # ensures reproducibility
) -> tuple[LatentDirichletAllocation, np.ndarray]:
    """
    Fit a Latent Dirichlet Allocation model on a document-term matrix.

    Uses online learning (mini-batch variational Bayes) for scalability.
    Set random_state for reproducibility within the same environment; note
    that results may still differ across library versions or hardware.

    Args:
        dtm:          Sparse document-term matrix from create_dtm().
        n_topics:     Number of latent topics to infer.
        random_state: Random seed for the LDA initialisation.

    Returns:
        lda_model:  Fitted LatentDirichletAllocation instance.
        lda_output: Document-topic probability matrix of shape (n_docs, n_topics).
    """
    lda_model = LatentDirichletAllocation(
        n_components=n_topics,
        random_state=random_state,
        learning_method="online",
        max_iter=20,
    )
    lda_output = lda_model.fit_transform(dtm)
    return lda_model, lda_output


# ─────────────────────────────────────────────────────────────────────────────
# STEP 6 — TOPIC TERMS
# ─────────────────────────────────────────────────────────────────────────────

def get_topic_terms(
    model:         LatentDirichletAllocation,
    feature_names: np.ndarray,
    keyword:       str,
    n_top_words:   int,
    n_topics:      int,
    out_dir:       Path,
    dtm:           object,
) -> dict[int, list[str]]:
    """
    Extract and save the top terms for each LDA topic.

    For every topic, saves a CSV with per-term rank, overall corpus frequency,
    and within-topic probability. Also saves a summary CSV with the top-N
    terms for all topics side by side.

    Args:
        model:         Fitted LDA model.
        feature_names: Vocabulary array from vectorizer.get_feature_names_out().
        keyword:       Concept label, used in output filenames.
        n_top_words:   Number of top terms to extract per topic.
        n_topics:      Total number of topics (used in output filenames).
        out_dir:       Directory where output CSVs are saved.
        dtm:           Document-term matrix (used to compute overall term frequencies).

    Returns:
        Dict mapping topic index (0-based) → list of top term strings.
    """
    topic_term_freq_dir = Path(out_dir) / "topic_term_frequencies"
    topic_term_freq_dir.mkdir(parents=True, exist_ok=True)

    # Overall term frequency summed across all documents
    overall_term_freq = np.asarray(dtm.sum(axis=0)).flatten()

    # Normalised per-topic term distribution: p(word | topic)
    topic_term_freq = model.components_ / model.components_.sum(axis=1, keepdims=True)

    topics = {}
    for topic_idx, topic in enumerate(model.components_):
        top_indices = topic.argsort()[: -n_top_words - 1 : -1]

        topic_data = [
            {
                "rank":                                                 rank,
                "term":                                                 feature_names[i],
                "overall_term_freq_all_topics":                         overall_term_freq[i],
                "estimated_term_freq_within_topic_before_normalization": model.components_[topic_idx, i],
                "estimated_term_freq_within_topic":                     topic_term_freq[topic_idx, i],
            }
            for rank, i in enumerate(top_indices, start=1)
        ]

        topics[topic_idx] = [d["term"] for d in topic_data]

        pd.DataFrame(topic_data).to_csv(
            topic_term_freq_dir / f"topic_term_freq_{keyword}_topic{topic_idx + 1}_{n_topics}.csv",
            index=False,
        )

    # Summary: top-N terms for all topics side by side
    summary_df = pd.DataFrame(topics)
    summary_df.columns = [f"Topic_{i + 1}" for i in range(len(topics))]
    summary_df.index   = [f"Term_{i + 1}" for i in range(n_top_words)]
    summary_df.to_csv(out_dir / f"topic_terms_{keyword}_{n_topics}.csv", index=False)
    print(f"  Top terms saved: topic_terms_{keyword}_{n_topics}.csv")

    return topics


# ─────────────────────────────────────────────────────────────────────────────
# STEP 7 — DOCUMENT-TOPIC ASSIGNMENTS
# ─────────────────────────────────────────────────────────────────────────────

def get_document_topics(
    model:        LatentDirichletAllocation,
    dtm:          object,
    topic_terms:  dict[int, list[str]],
    excerpts:     list[dict],
    keyword:      str,
    n_top_topics: int,
    out_dir:      Path,
    n_topics:     int,
) -> None:
    """
    Assign the dominant topic to each document and save the results.

    For each document, identifies the single most probable topic and its
    probability. Metadata from the original excerpt is included in the output.

    Args:
        model:        Fitted LDA model.
        dtm:          Document-term matrix used for inference.
        topic_terms:  Dict mapping topic index → list of top terms (from get_topic_terms).
        excerpts:     List of excerpt dicts (used to attach metadata to each row).
        keyword:      Concept label, used in output filename.
        n_top_topics: Not currently used; reserved for future multi-topic output.
        out_dir:      Directory where the output CSV is saved.
        n_topics:     Total number of topics, used in output filename.
    """
    doc_topic_probs = model.transform(dtm)

    results = []
    for doc_idx, doc_probs in enumerate(doc_topic_probs):
        top_topic_idx = doc_probs.argmax()
        results.append({
            "document_id":                    doc_idx,
            "most_prevalent_topic_id":        top_topic_idx + 1,   # 1-based for readability
            "most_prevalent_topic_probability": doc_probs[top_topic_idx],
            **excerpts[doc_idx],
        })

    summary_df = pd.DataFrame(results)
    summary_df.to_csv(out_dir / f"doc_top_topics_{keyword}_{n_topics}.csv", index=False)
    print(f"  Document topics saved: doc_top_topics_{keyword}_{n_topics}.csv")


# ─────────────────────────────────────────────────────────────────────────────
# STEP 8 — PYLDAVIS VISUALISATION
# ─────────────────────────────────────────────────────────────────────────────

def create_pyldavis(
    model:      LatentDirichletAllocation,
    dtm:        object,
    vectorizer: CountVectorizer,
    keyword:    str,
    n_topics:   int,
    out_dir:    Path,
) -> object:
    """
    Create and save an interactive pyLDAvis visualisation as an HTML file.

    Uses t-SNE for the inter-topic distance map. Topics are shown in their
    original order (sort_topics=False) to match the topic IDs in other outputs.

    Args:
        model:      Fitted LDA model.
        dtm:        Document-term matrix.
        vectorizer: Fitted CountVectorizer (provides term names and frequencies).
        keyword:    Concept label, used in output filename.
        n_topics:   Total number of topics, used in output filename.
        out_dir:    Directory where the HTML file is saved.

    Returns:
        pyLDAvis PreparedData object.
    """
    print("  Creating pyLDAvis visualisation …")
    vis_data = pyLDAvis.lda_model.prepare(model, dtm, vectorizer, mds="tsne", sort_topics=False)
    out_path = out_dir / f"lda_vis_{keyword}_{n_topics}.html"
    pyLDAvis.save_html(vis_data, str(out_path))
    print(f"  Visualisation saved: {out_path.name}")
    return vis_data


# ─────────────────────────────────────────────────────────────────────────────
# STEP 9 — MODEL STATISTICS
# ─────────────────────────────────────────────────────────────────────────────

def get_stats(
    lda_model: LatentDirichletAllocation,
    dtm:       object,
    keyword:   str,
    out_dir:   Path,
) -> None:
    """
    Compute and save corpus-level and per-topic diagnostic statistics.

    Corpus-level metrics: document count, vocabulary size, token count,
    average document length, perplexity, and log-likelihood.

    Per-topic metrics: mean topic prevalence across documents, number of
    documents for which the topic is dominant, and peakiness (a proxy for
    topic coherence — higher means the topic mass is concentrated on fewer terms).

    Outputs are saved under out_dir/stats/.

    Args:
        lda_model: Fitted LDA model.
        dtm:       Document-term matrix.
        keyword:   Concept label, used in output filenames.
        out_dir:   Parent output directory; a 'stats' subdirectory is created.
    """
    stats_dir = Path(out_dir) / "stats"
    stats_dir.mkdir(parents=True, exist_ok=True)

    n_documents = dtm.shape[0]
    n_terms     = dtm.shape[1]
    n_tokens    = int(dtm.sum())
    n_topics    = lda_model.components_.shape[0]

    doc_topic_matrix = lda_model.transform(dtm)

    # Per-topic prevalence: mean probability assigned to each topic across docs
    topic_prevalence = doc_topic_matrix.mean(axis=0)

    # Token-weighted prevalence: share of total pseudo-counts per topic
    topic_prevalence_token_weighted = (
        lda_model.components_.sum(axis=1) / lda_model.components_.sum()
    )

    # Peakiness: ratio of max to mean term weight — higher = more concentrated topic
    topic_peakiness = lda_model.components_.max(axis=1) / lda_model.components_.mean(axis=1)

    # Number of documents for which each topic is the dominant one
    n_docs_per_topic = (
        (doc_topic_matrix.argmax(axis=1)[:, None] == np.arange(n_topics)).sum(axis=0)
    )

    global_summary = {
        "n_documents":   int(n_documents),
        "n_terms":       int(n_terms),
        "n_tokens":      int(n_tokens),
        "n_topics":      int(n_topics),
        "avg_doc_length": round(n_tokens / n_documents, 1),
        "perplexity":    round(lda_model.perplexity(dtm), 2),
        "log_likelihood": round(lda_model.score(dtm), 2),
    }

    topic_summary = pd.DataFrame({
        "topic_id":              range(1, n_topics + 1),
        "topic_prevalence":      topic_prevalence,
        "n_docs_where_dominant": n_docs_per_topic,
        "peakiness":             topic_peakiness,
    }).round(4).sort_values("topic_prevalence", ascending=False)
    topic_summary.insert(0, "topic_rank", range(1, n_topics + 1))

    # Global summary as a two-column metric/value table
    pd.Series(global_summary).reset_index().rename(
        columns={"index": "metric", 0: "value"}
    ).to_csv(stats_dir / f"global_summary_{keyword}_{n_topics}.csv", index=False)

    topic_summary.to_csv(stats_dir / f"topic_summary_{keyword}_{n_topics}.csv", index=False)
    print(f"  Stats saved to {stats_dir.name}/")


# ─────────────────────────────────────────────────────────────────────────────
# ORCHESTRATION — SINGLE CONCEPT × SINGLE N_TOPICS
# ─────────────────────────────────────────────────────────────────────────────

def run_topic_model(
    df:          pd.DataFrame,
    out_dir:     Path,
    keyword:     str | None = None,
    n_topics:    int   = 10,
    n_top_words: int   = 10,
    n_top_topics: int  = 3,
    max_df:      float = 0.95,
    min_df:      int   = 5,
) -> tuple:
    """
    Run the full LDA topic modelling pipeline for one concept and one topic count.

    Steps:
      2. Get excerpts for the concept
      3. Preprocess text
      4. Build document-term matrix
      5. Train LDA model
      6. Extract top terms per topic
      7. Assign dominant topic per document
      8. Create pyLDAvis visualisation
      9. Compute and save statistics

    Args:
        df:           Full results DataFrame.
        out_dir:      Output directory for this concept × n_topics combination.
        keyword:      Concept label to filter by (None = all concepts).
        n_topics:     Number of topics for this run.
        n_top_words:  Number of top terms to extract per topic.
        n_top_topics: Number of top topics to consider per document.
        max_df:       Maximum document frequency for CountVectorizer.
        min_df:       Minimum document frequency for CountVectorizer.

    Returns:
        topic_terms, lda_model, lda_output, dtm, excerpts, vis, feature_names
    """
    print(f"  Running LDA: keyword='{keyword}', n_topics={n_topics}")

    # Step 2: Get excerpts for the concept
    excerpts = get_excerpts(df, keyword)
    # Step 3: Preprocess text
    preprocessed = preprocess_text(excerpts)
    # Step 4: Build document-term matrix
    dtm, vectorizer = create_dtm(preprocessed, max_df=max_df, min_df=min_df)
    feature_names   = vectorizer.get_feature_names_out()
    # Step 5: Train LDA model
    lda_model, lda_output = train_lda(dtm, n_topics)
    # Step 6: Extract top terms per topic
    topic_terms = get_topic_terms(lda_model, feature_names, keyword, n_top_words, n_topics, out_dir, dtm)
    # Step 7: Assign dominant topic per document
    get_document_topics(lda_model, dtm, topic_terms, excerpts, keyword, n_top_topics, out_dir, n_topics)
    # Step 8: Create pyLDAvis visualisation
    vis = create_pyldavis(lda_model, dtm, vectorizer, keyword, n_topics, out_dir)
    # Step 9: Compute and save statistics
    get_stats(lda_model, dtm, keyword, out_dir)

    return topic_terms, lda_model, lda_output, dtm, excerpts, vis, feature_names


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def run_lda(keywords: list[str], result_df: pd.DataFrame) -> None:
    """
    Run the LDA pipeline for all concepts and all topic counts.

    For each concept × n_topics combination, a separate output directory is
    created and the fitted model is saved as a pickle.

    Args:
        keywords:  List of concept labels to model.
        result_df: Full keyword search results DataFrame.
    """
    for keyword in keywords:
        for n_topics in N_TOPICS_LIST:
            print("=" * 60)
            print(f"  Concept: {keyword}  |  n_topics: {n_topics}")
            print("=" * 60)

            out_dir = OUT_DIR / keyword / str(n_topics)
            out_dir.mkdir(parents=True, exist_ok=True)

            topic_terms, lda_model, lda_output, dtm, excerpts, vis, feature_names = run_topic_model(
                result_df,
                keyword=keyword,
                out_dir=out_dir,
                n_topics=n_topics,
                n_top_words=20,
                n_top_topics=3,
                max_df=0.8,
                min_df=5,
            )

            # Save fitted model for reproducibility
            tm_dir = out_dir / "tm"
            tm_dir.mkdir(parents=True, exist_ok=True)
            with open(tm_dir / f"lda_model_{keyword}_{n_topics}.pkl", "wb") as f:
                pickle.dump(lda_model, f)
            print(f"  Model saved: lda_model_{keyword}_{n_topics}.pkl")


def main() -> None:
    """
    Entry point for the LDA topic modelling pipeline.

    Steps:
      1. Load keywords and search results
      2–9. Run topic modelling for each concept × n_topics combination
           (see run_topic_model for per-run steps)
    """
    # Step 1 — Load inputs
    keywords  = load_keywords(KEYWORD_PATH)
    result_df = load_data(DATA_PATH)

    # Steps 2–9 — Run LDA for all concepts and topic counts
    run_lda(keywords, result_df)


if __name__ == "__main__":
    main()