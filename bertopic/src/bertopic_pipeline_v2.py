#!/usr/bin/env python3
# ══════════════════════════════════════════════════════════════════════════
#  bertopic_pipeline.py
# ──────────────────────────────────────────────────────────────────────────
#  Evo-Buch Curriculum-Atlas — Master Data Generation Pipeline
# ──────────────────────────────────────────────────────────────────────────
#
#  PURPOSE
#  -------
#  Converts a raw CSV of German curriculum text excerpts (one row per
#  excerpt × matched search concept) into everything the client-side
#  "Curriculum Atlas" web app needs:
#
#    data/<Concept>.json   – one file per concept, array of records:
#                            { id, state, subject, grade_band, topic,
#                              is_outlier, umap_2d, umap_3d, excerpt }
#    data/manifest.json    – corpus-wide index (concepts, subjects, states,
#                            topics, counts, coordinate bounding boxes,
#                            checksums, generation timestamp) so the
#                            front-end can build UI controls without
#                            downloading every concept file up front.
#
#  Intermediate artefacts (embeddings, UMAP coordinates, fitted BERTopic
#  models, distribution statistics) are cached under `cache/` and `out/`
#  so that re-running the script is cheap and deterministic.
#
#  PIPELINE OVERVIEW
#  ------------------
#    1. Load & validate the raw CSV.
#    2. Compute (or load cached) sentence embeddings for the ENTIRE corpus
#       once — this is the expensive step and is shared across concepts.
#    3. For each of the 22 target concepts:
#         a. Slice the rows belonging to that concept.
#         b. Slice the corresponding embeddings (no re-encoding).
#         c. Fit (or load cached) a BERTopic model on the concept subset.
#         d. Fit (or load cached) a concept-local 2D and 3D UMAP projection.
#         e. Derive human-readable topic labels (auto + optional manual
#            overrides).
#         f. Clean/normalise metadata (state names, subject names,
#            grade → grade-band bucketing).
#         g. Compute topic × subject distribution statistics (diagnostics).
#         h. Export data/<Concept>.json.
#    4. Build & write data/manifest.json summarising everything above.
#
#  REPRODUCIBILITY
#  ----------------
#  - A single RANDOM_SEED drives numpy, UMAP and HDBSCAN.
#  - The source CSV is checksummed (MD5); the checksum is embedded in the
#    manifest so downstream consumers can detect stale data.
#  - Every cache file is namespaced by concept, so partial re-runs are safe.
#  - All non-deterministic external calls (model downloads) are cached.
#
#  USAGE
#  -----
#    python bertopic_pipeline.py --csv data_raw/results.csv
#    python bertopic_pipeline.py --concepts Evolution,Kultur --force-topics
#    python bertopic_pipeline.py --dry-run
#
#  REQUIREMENTS
#  ------------
#    pandas, numpy, scipy, scikit-learn, spacy, tqdm,
#    bertopic, umap-learn, hdbscan, sentence-transformers
#
# ══════════════════════════════════════════════════════════════════════════

from __future__ import annotations

# ── Standard library ─────────────────────────────────────────────────────
import argparse
import hashlib
import json
import logging
import random
import re
import sys
import traceback
import unicodedata
import warnings
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

# ── Third-party (numeric / ML core) ──────────────────────────────────────
try:
    import numpy as np
    import pandas as pd
    from scipy.stats import entropy
except ImportError as e:
    sys.exit(f"[FATAL] Missing core dependency: {e}. Run: pip install numpy pandas scipy")

try:
    from tqdm import tqdm
except ImportError:
    # tqdm is a UX nicety, not a hard requirement — degrade gracefully.
    def tqdm(iterable, *args, **kwargs):
        return iterable

try:
    from umap import UMAP
except ImportError as e:
    sys.exit(f"[FATAL] Missing dependency 'umap-learn': {e}. Run: pip install umap-learn")

try:
    from hdbscan import HDBSCAN
except ImportError as e:
    sys.exit(f"[FATAL] Missing dependency 'hdbscan': {e}. Run: pip install hdbscan")

try:
    from bertopic import BERTopic
    from sklearn.feature_extraction.text import CountVectorizer
except ImportError as e:
    sys.exit(f"[FATAL] Missing dependency 'bertopic'/'scikit-learn': {e}. "
              f"Run: pip install bertopic scikit-learn")

sys.path.append(str(Path(__file__).resolve().parent.parent.parent))
try:
    from shared_stopwords import stopwords_for_concept
except ImportError as e:
    sys.exit(f"[FATAL] Could not import shared_stopwords.py from repo root: {e}")

import pickle


# ══════════════════════════════════════════════════════════════════════════
#  CONFIGURATION
# ══════════════════════════════════════════════════════════════════════════

# The 22 core evolutionary-anthropology concepts tracked across the corpus.
# Order here defines default processing order and default UI ordering hints
# written into the manifest.
DEFAULT_CONCEPTS: list[str] = [
    "Anpassung", "Anthropologie", "Bedürfnis", "Emotion", "Evolution",
    "Freiheit", "Gefühl", "Gen", "Gerechtigkeit", "Glück", "Handeln",
    "Konkurrenz", "Kooperation", "Kultur", "Mensch", "Moral", "Norm",
    "Rationalität", "Ursache", "Verhalten", "Vorurteil", "Wert",
]

# Sentence-embedding model. paraphrase-multilingual-MiniLM-L12-v2 replaced
# all-MiniLM-L6-v2 on 2026-07-21: the latter is trained overwhelmingly on
# English sentence pairs despite the old comment here calling it
# "multilingual-capable", and produced under-differentiated embeddings for
# German curriculum text (e.g. Verhalten's 1,155-doc corpus collapsed to 4
# clusters with a 0% outlier rate under the old model vs. 23 clusters /
# 19% outliers under this one -- see METHODOLOGY.md SS3 for the full pilot).
EMBEDDING_MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"

# Topic-count CEILING (approved 2026-07-21, "Strategy B", METHODOLOGY.md
# section 4): app_specs.md requires "no more than ten topics plus one
# outlier topic" per concept. BERTopic's nr_topics/_reduce_topics() counts
# the outlier bucket (-1) toward this total when outliers exist, so 11 ->
# up to 10 real topics + 1 outlier. Critically, reduce_topics only MERGES
# DOWN when a concept's natural topic count exceeds this value -- it never
# inflates a concept that naturally settles below it (self._outliers is
# subtracted before AgglomerativeClustering(n=nr_topics - outliers) runs,
# and reduction is skipped entirely when nr_topics >= the natural count).
# So passing this uniformly is already the full "ceiling not target"
# behavior -- no extra custom logic needed on top of BERTopic's own.
DEFAULT_NR_TOPICS_CEILING = 11


def embedding_model_slug() -> str:
    """Filesystem-safe stand-in for EMBEDDING_MODEL_NAME, used to namespace
    every embedding-derived cache path (global embeddings, per-concept
    BERTopic models, per-concept UMAP projections) so switching models
    can't silently resurrect a stale cache fit on the previous model's
    embeddings -- see compute_or_load_embeddings() for the incident this
    fixes (METHODOLOGY.md section 3/6).
    """
    return re.sub(r"[^a-zA-Z0-9_-]+", "_", EMBEDDING_MODEL_NAME)

# A single seed drives every stochastic component (numpy, UMAP, HDBSCAN)
# so that re-running the pipeline on unchanged input yields identical output.
RANDOM_SEED = 42

# Raw CSV -> internal column names. Centralising this mapping means a schema
# change in the source data only requires editing this dict, not the logic
# below.
COLUMN_MAP = {
    "text":    "text_excerpt",
    "concept": "search_term",
    "match":   "match_term",
    "state":   "state",
    "school":  "school type",
    "grade":   "grade",
    "year":    "year",
    "subject": "subject",
}

# Canonical German federal states + best-effort alias resolution. Any raw
# 'state' value not matched here falls through to a Title-Case pass-through
# and is logged for manual review (out/unmapped_states.txt).
CANONICAL_STATES = [
    "Baden-Württemberg", "Bayern", "Berlin", "Brandenburg", "Bremen",
    "Hamburg", "Hessen", "Mecklenburg-Vorpommern", "Niedersachsen",
    "Nordrhein-Westfalen", "Rheinland-Pfalz", "Saarland", "Sachsen",
    "Sachsen-Anhalt", "Schleswig-Holstein", "Thüringen",
]
STATE_ALIASES = {
    "bw": "Baden-Württemberg", "baden wuerttemberg": "Baden-Württemberg",
    "baden-wuerttemberg": "Baden-Württemberg", "bawu": "Baden-Württemberg",
    "by": "Bayern", "bayern": "Bayern",
    "be": "Berlin", "berlin": "Berlin",
    "bb": "Brandenburg", "brandenburg": "Brandenburg",
    "hb": "Bremen", "bremen": "Bremen",
    "hh": "Hamburg", "hamburg": "Hamburg",
    "he": "Hessen", "hessen": "Hessen",
    "mv": "Mecklenburg-Vorpommern", "meckpomm": "Mecklenburg-Vorpommern",
    "mecklenburg vorpommern": "Mecklenburg-Vorpommern",
    "mecklenburg-vorpommern": "Mecklenburg-Vorpommern",
    "ni": "Niedersachsen", "niedersachsen": "Niedersachsen",
    "nrw": "Nordrhein-Westfalen",
    "nordrhein westfalen": "Nordrhein-Westfalen",
    "nordrhein-westfalen": "Nordrhein-Westfalen",
    "rp": "Rheinland-Pfalz", "rlp": "Rheinland-Pfalz",
    "rheinland pfalz": "Rheinland-Pfalz", "rheinland-pfalz": "Rheinland-Pfalz",
    "sl": "Saarland", "saarland": "Saarland",
    "sn": "Sachsen", "sachsen": "Sachsen",
    "st": "Sachsen-Anhalt", "sachsen anhalt": "Sachsen-Anhalt",
    "sachsen-anhalt": "Sachsen-Anhalt",
    "sh": "Schleswig-Holstein", "schleswig holstein": "Schleswig-Holstein",
    "schleswig-holstein": "Schleswig-Holstein",
    "th": "Thüringen", "thueringen": "Thüringen", "thüringen": "Thüringen",
}

# Grade → grade-band bucketing. Bands roughly follow the German Sek I / Sek
# II structure; adjust boundaries here if the curriculum atlas needs finer
# granularity (e.g. splitting 11-13 into 11 / 12-13).
GRADE_BANDS = [
    (1, 4,  "1-4"),
    (5, 6,  "5-6"),
    (7, 8,  "7-8"),
    (9, 10, "9-10"),
    (11, 13, "11-13"),
]
# Free-text grade markers (Oberstufe course phases etc.) that don't carry a
# numeric grade but map cleanly onto a band.
GRADE_TEXT_HINTS = {
    "ef": "11-13", "q1": "11-13", "q2": "11-13", "q3": "11-13", "q4": "11-13",
    "einführungsphase": "11-13", "qualifikationsphase": "11-13",
    "oberstufe": "11-13", "sek ii": "11-13", "sekii": "11-13",
    "sek i": "7-10", "seki": "7-10",
}

UNKNOWN_LABEL = "Unbekannt"


# ══════════════════════════════════════════════════════════════════════════
#  CLI / RUNTIME CONFIG
# ══════════════════════════════════════════════════════════════════════════

@dataclass
class RunConfig:
    """Resolved runtime configuration (CLI args + derived paths)."""
    base_dir: Path
    csv_path: Path
    web_data_dir: Path   # -> data/            (consumed by curriculum_atlas.html)
    cache_dir: Path      # -> cache/           (embeddings, umap, bertopic models)
    out_dir: Path        # -> out/             (stats CSVs, logs, static plots)
    concepts: list[str]
    force_embeddings: bool
    force_umap: bool
    force_topics: bool
    skip_stats: bool
    dry_run: bool
    pretty_json: bool
    nr_topics: Optional[int]
    log_level: str
    topic_overrides_path: Path


def parse_args(argv: Optional[list[str]] = None) -> RunConfig:
    """Parse CLI arguments and resolve all working paths.

    Centralising path resolution here (rather than as bare module constants)
    makes the pipeline portable across machines/CI runners — nothing is
    hardcoded to a specific user's filesystem.
    """
    base_dir = Path(__file__).resolve().parent

    p = argparse.ArgumentParser(
        description="Evo-Buch Curriculum-Atlas: BERTopic data generation pipeline.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    default_csv = base_dir / "data_raw" / "results.csv"
    if not default_csv.exists():
        default_csv = base_dir.parent.parent / "keyword_search" / "out" / "results.csv"
    p.add_argument("--csv", type=Path, default=default_csv,
                    help="Path to the raw source CSV. Defaults to data_raw/results.csv, "
                         "or keyword_search/out/results.csv if the former is absent.")
    p.add_argument("--web-data-dir", type=Path, default=base_dir / "data",
                    help="Output dir for JSON consumed by curriculum_atlas.html.")
    p.add_argument("--cache-dir", type=Path, default=base_dir / "cache",
                    help="Cache dir for embeddings / UMAP coords / BERTopic models.")
    p.add_argument("--out-dir", type=Path, default=base_dir / "out",
                    help="Output dir for stats CSVs, logs and static plots.")
    p.add_argument("--concepts", type=str, default=None,
                    help="Comma-separated subset of concepts to (re)process. "
                         "Default: all 22 core concepts.")
    p.add_argument("--topic-overrides", type=Path,
                    default=base_dir / "topic_label_overrides.json",
                    help="Optional JSON file of manual topic-label overrides: "
                         '{"Concept": {"0": "Custom label", ...}}')
    p.add_argument("--force-embeddings", action="store_true",
                    help="Recompute embeddings even if cached.")
    p.add_argument("--force-umap", action="store_true",
                    help="Recompute UMAP projections even if cached.")
    p.add_argument("--force-topics", action="store_true",
                    help="Refit BERTopic models even if cached.")
    p.add_argument("--skip-stats", action="store_true",
                    help="Skip topic/subject distribution-statistics export.")
    p.add_argument("--nr-topics", type=int, default=DEFAULT_NR_TOPICS_CEILING,
                    help="Topic-count CEILING per concept, passed straight to "
                         "BERTopic's own nr_topics/reduce_topics. Per BERTopic's "
                         "_reduce_topics(), this only merges down when a concept's "
                         "natural (min_cluster_size-driven) topic count exceeds the "
                         "ceiling -- it never inflates a concept that naturally "
                         "settles below it. Pass 0 or a negative value for "
                         "uncapped/auto (the old default, not recommended -- see "
                         "METHODOLOGY.md section 4).")
    p.add_argument("--minify-json", dest="pretty_json", action="store_false",
                    help="Write compact (minified) JSON instead of indented.")
    p.add_argument("--dry-run", action="store_true",
                    help="Validate CSV/config and print the plan; no computation.")
    p.add_argument("--log-level", default="INFO",
                    choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    args = p.parse_args(argv)

    nr_topics = args.nr_topics if args.nr_topics and args.nr_topics > 0 else None

    concepts = DEFAULT_CONCEPTS
    if args.concepts:
        requested = [c.strip() for c in args.concepts.split(",") if c.strip()]
        unknown = [c for c in requested if c not in DEFAULT_CONCEPTS]
        if unknown:
            print(f"[WARN] Unrecognised concept(s) requested (processing anyway): {unknown}")
        concepts = requested

    return RunConfig(
        base_dir=base_dir,
        csv_path=args.csv,
        web_data_dir=args.web_data_dir,
        cache_dir=args.cache_dir,
        out_dir=args.out_dir,
        concepts=concepts,
        force_embeddings=args.force_embeddings,
        force_umap=args.force_umap,
        force_topics=args.force_topics,
        skip_stats=args.skip_stats,
        dry_run=args.dry_run,
        pretty_json=args.pretty_json,
        nr_topics=nr_topics,
        log_level=args.log_level,
        topic_overrides_path=args.topic_overrides,
    )


# ══════════════════════════════════════════════════════════════════════════
#  LOGGING & REPRODUCIBILITY HELPERS
# ══════════════════════════════════════════════════════════════════════════

def setup_logging(out_dir: Path, level: str) -> logging.Logger:
    """Configure a logger that writes to both stdout and a run log file."""
    out_dir.mkdir(parents=True, exist_ok=True)
    log_path = out_dir / "pipeline.log"

    logger = logging.getLogger("curriculum_atlas")
    logger.setLevel(getattr(logging, level))
    logger.handlers.clear()

    fmt = logging.Formatter("%(asctime)s [%(levelname)-7s] %(message)s",
                             datefmt="%H:%M:%S")
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(fmt)
    file_handler = logging.FileHandler(log_path, mode="a", encoding="utf-8")
    file_handler.setFormatter(fmt)

    logger.addHandler(stream_handler)
    logger.addHandler(file_handler)
    return logger


def set_global_seed(seed: int = RANDOM_SEED) -> None:
    """Seed every stochastic library the pipeline touches."""
    random.seed(seed)
    np.random.seed(seed)


def md5_of_file(path: Path, chunk_size: int = 2 ** 20) -> str:
    """Compute the MD5 checksum of a file (used to fingerprint the source CSV)."""
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(chunk_size), b""):
            h.update(chunk)
    return h.hexdigest()


# ══════════════════════════════════════════════════════════════════════════
#  METADATA NORMALISATION HELPERS
# ══════════════════════════════════════════════════════════════════════════

def _strip_diacritics(s: str) -> str:
    """Normalise unicode so alias-matching is accent/case insensitive."""
    nfkd = unicodedata.normalize("NFKD", s)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def canonicalize_state(raw: Any, unmapped_tracker: Counter) -> str:
    """Map a raw, messy 'state' string onto one of the 16 canonical German
    federal state names. Unknown values are Title-Cased and tallied in
    `unmapped_tracker` so they can be reviewed/added to STATE_ALIASES later.
    """
    # KMK-issued national documents (Bildungsstandards, EPA, etc.) have no
    # Bundesland by design -- keyword_search.py treats these the same way
    # (state left unset for KMK-prefixed filenames). So a missing/blank state
    # means "KMK", not "Unbekannt".
    if raw is None or (isinstance(raw, float) and np.isnan(raw)):
        return "KMK"
    text = str(raw).strip()
    if not text:
        return "KMK"

    key = _strip_diacritics(text).lower().strip()
    if key in ("<na>", "na", "n/a", "none", "nan"):
        return "KMK"
    if key == "kmk":
        return "KMK"
    if key in STATE_ALIASES:
        return STATE_ALIASES[key]
    # Direct match against canonical list (case-insensitive, accent-insensitive)
    for canon in CANONICAL_STATES:
        if _strip_diacritics(canon).lower() == key:
            return canon

    unmapped_tracker[text] += 1
    return text.title()


def derive_grade_band(raw: Any) -> str:
    """Bucket a messy raw 'grade' field into one of the coarse GRADE_BANDS.

    Handles: single grades ("9"), ranges ("9-10", "9/10"), textual course
    phases ("Q1", "EF", "Sek II"), and missing/garbage values.
    """
    if raw is None or (isinstance(raw, float) and np.isnan(raw)):
        return UNKNOWN_LABEL
    text = str(raw).strip().lower()
    if not text:
        return UNKNOWN_LABEL

    # Textual hints (Oberstufe phase codes) take priority if no digits present.
    numbers = [int(n) for n in re.findall(r"\d+", text)]
    if not numbers:
        for hint, band in GRADE_TEXT_HINTS.items():
            if hint in text:
                return band
        return UNKNOWN_LABEL

    lo = min(numbers)
    for band_lo, band_hi, label in GRADE_BANDS:
        if band_lo <= lo <= band_hi:
            return label
    # Numbers outside the known bands (e.g. grade > 13) — pass through raw.
    return f"{lo}"


def clean_subject(raw: Any) -> str:
    """Trim/normalise the 'subject' field; empty values become 'Unbekannt'."""
    if raw is None or (isinstance(raw, float) and np.isnan(raw)):
        return UNKNOWN_LABEL
    text = str(raw).strip()
    return text if text else UNKNOWN_LABEL


# ══════════════════════════════════════════════════════════════════════════
#  STEP 1 — LOAD & VALIDATE SOURCE CSV
# ══════════════════════════════════════════════════════════════════════════

def load_source_csv(csv_path: Path, log: logging.Logger) -> pd.DataFrame:
    """Load the raw CSV, validate required columns exist, and coerce dtypes
    to plain Python objects (Arrow-backed dtypes have caused friction with
    BERTopic / sentence-transformers in the past).
    """
    if not csv_path.exists():
        raise FileNotFoundError(f"Source CSV not found: {csv_path}")

    log.info(f"Loading source CSV from {csv_path} …")
    df = pd.read_csv(csv_path, low_memory=False, dtype_backend="numpy_nullable")

    required = list(COLUMN_MAP.values())
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Source CSV is missing required column(s): {missing}. "
                          f"Update COLUMN_MAP if the schema has changed.")

    for col in df.columns:
        try:
            df[col] = df[col].astype(object)
        except Exception:
            pass

    # Drop rows with empty/NaN text excerpts — they cannot be embedded.
    n_before = len(df)
    df = df[df[COLUMN_MAP["text"]].notna()]
    df = df[df[COLUMN_MAP["text"]].astype(str).str.strip() != ""]
    n_after = len(df)
    if n_after < n_before:
        log.warning(f"Dropped {n_before - n_after} row(s) with empty text_excerpt.")

    # Preserve the ORIGINAL index as an explicit 'doc_id' column before any
    # further filtering — this is the stable key used to align concept-level
    # slices back to the global embedding matrix.
    df = df.reset_index(drop=True)
    df["doc_id"] = df.index

    log.info(f"  Loaded {len(df):,} rows × {df.shape[1]} columns.")
    return df


# ══════════════════════════════════════════════════════════════════════════
#  STEP 2 — GLOBAL SENTENCE EMBEDDINGS
# ══════════════════════════════════════════════════════════════════════════

def compute_or_load_embeddings(
    docs: list[str], cache_dir: Path, log: logging.Logger, force: bool = False,
) -> np.ndarray:
    """Compute (or load cached) L2-normalised sentence embeddings for the
    full corpus. This is the single most expensive step, so it is computed
    exactly once and reused across every concept's BERTopic run.

    The cache filename is namespaced by embedding model name -- without
    this, switching EMBEDDING_MODEL_NAME (as happened 2026-07-21, see
    METHODOLOGY.md section 3) would silently reuse a stale cache computed
    under the old model, since the old filename carried no model identity.
    """
    cache_path = cache_dir / f"embeddings_all__{embedding_model_slug()}.npy"
    if cache_path.exists() and not force:
        log.info("Loading global embeddings from cache …")
        emb = np.load(cache_path)
        log.info(f"  Loaded embeddings: shape {emb.shape}")
        return emb

    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as e:
        raise SystemExit(f"[FATAL] Missing 'sentence-transformers': {e}. "
                          f"Run: pip install sentence-transformers")

    log.info(f"Encoding {len(docs):,} documents with '{EMBEDDING_MODEL_NAME}' …")
    model = SentenceTransformer(EMBEDDING_MODEL_NAME)
    emb = model.encode(
        docs, batch_size=256, show_progress_bar=True,
        normalize_embeddings=True, convert_to_numpy=True,
    )
    cache_dir.mkdir(parents=True, exist_ok=True)
    np.save(cache_path, emb)
    log.info(f"  Saved embeddings cache: shape {emb.shape} -> {cache_path}")
    return emb


# ══════════════════════════════════════════════════════════════════════════
#  STEP 3 — GENERIC UMAP PROJECTION (2D / 3D, GLOBAL / LOCAL)
# ══════════════════════════════════════════════════════════════════════════

def compute_or_load_umap(
    embeddings: np.ndarray,
    cache_path: Path,
    n_components: int,
    log: logging.Logger,
    n_neighbors: int = 20,
    min_dist: float = 0.05,
    spread: float = 1.2,
    metric: str = "cosine",
    force: bool = False,
) -> np.ndarray:
    """Fit (or load cached) a UMAP projection.

    A single generic function serves every projection the pipeline needs
    (global 2D/3D diagnostic plots, concept-local 2D/3D exported to the
    web app) — this avoids four near-duplicate implementations drifting
    out of sync.

    Small corpora are handled gracefully: `n_neighbors` is clamped to
    `n_samples - 1`, and degenerate corpora (<= n_components + 1 rows) fall
    back to a zero-padded / jittered layout rather than crashing UMAP.
    """
    if cache_path.exists() and not force:
        coords = np.load(cache_path)
        log.info(f"  Loaded UMAP cache ({n_components}D): shape {coords.shape} "
                 f"<- {cache_path.name}")
        return coords

    n = embeddings.shape[0]
    if n <= n_components + 1:
        log.warning(f"  Corpus too small ({n} docs) for a stable "
                    f"{n_components}D UMAP fit — using jittered fallback layout.")
        rng = np.random.default_rng(RANDOM_SEED)
        coords = rng.normal(scale=0.1, size=(n, n_components))
    else:
        eff_neighbors = max(2, min(n_neighbors, n - 1))
        reducer = UMAP(
            n_neighbors=eff_neighbors, n_components=n_components,
            min_dist=min_dist, spread=spread, metric=metric,
            random_state=RANDOM_SEED, low_memory=False, verbose=False,
        )
        coords = reducer.fit_transform(embeddings)

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    np.save(cache_path, coords)
    log.info(f"  Fitted + cached UMAP ({n_components}D): shape {coords.shape} "
             f"-> {cache_path.name}")
    return coords


# ══════════════════════════════════════════════════════════════════════════
#  STEP 4 — CONCEPT-LEVEL DOCUMENT SLICING
# ══════════════════════════════════════════════════════════════════════════

def get_concept_documents(df: pd.DataFrame, concept: str) -> pd.DataFrame:
    """Slice the global dataframe down to rows matching a given concept,
    retaining the 'doc_id' alignment key needed for embedding lookups.
    """
    cols = [COLUMN_MAP[k] for k in
            ("text", "concept", "match", "state", "school", "grade", "year", "subject")]
    cols += ["doc_id"]
    sub = df.loc[df[COLUMN_MAP["concept"]] == concept, cols].copy()
    sub = sub.reset_index(drop=True)
    return sub


# ══════════════════════════════════════════════════════════════════════════
#  STEP 5 — BERTOPIC FIT (PER CONCEPT, CACHED)
# ══════════════════════════════════════════════════════════════════════════

def fit_or_load_bertopic(
    concept: str,
    docs: list[str],
    embeddings: np.ndarray,
    cache_dir: Path,
    log: logging.Logger,
    nr_topics: Optional[int] = None,
    force: bool = False,
) -> tuple[BERTopic, list[int]]:
    """Fit (or load cached) a BERTopic model for a single concept's document
    subset. Hyperparameters scale with corpus size; a fallback vectoriser
    (no min_df/max_df constraints) is used if the primary one raises
    (typical failure mode: max_df < min_df on very small/sparse corpora).

    Stopwords are resolved per concept via shared_stopwords.stopwords_for_concept()
    -- the shared Tier 1/2 base list plus this concept's own seed-term variants
    (Tier 3 self-seed exclusion, METHODOLOGY.md SS2), so e.g. "freiheit" is
    excluded from the Freiheit model's own vocabulary but remains ordinary,
    potentially informative vocabulary in every other concept's model.
    """
    german_stopwords = list(stopwords_for_concept(concept))
    cache_path = cache_dir / concept / f"topic_model_{concept}__{embedding_model_slug()}.pkl"

    if cache_path.exists() and not force:
        log.info(f"  [{concept}] Loading BERTopic model from cache …")
        with open(cache_path, "rb") as f:
            cached = pickle.load(f)
        return cached["model"], cached["topics"]

    n = len(docs)
    log.info(f"  [{concept}] Fitting BERTopic on {n:,} documents …")

    if n < 30:
        log.warning(f"  [{concept}] Very small corpus ({n} docs) — topic "
                    f"granularity will be limited.")

    # Corpus-size-adaptive vectoriser/clustering hyperparameters.
    if n < 200:
        min_df, max_df, min_cluster_size = 1, 1.0, max(3, n // 15)
    else:
        min_df, max_df, min_cluster_size = 3, 0.8, 15

    # UMAP for BERTopic's internal dimensionality reduction (distinct from,
    # and independent of, the 2D/3D projection we export to the web app).
    umap_model = UMAP(
        n_neighbors=min(15, max(2, n - 1)), n_components=min(5, max(2, n - 2)),
        min_dist=0.0, metric="cosine", random_state=RANDOM_SEED, low_memory=False,
    )
    hdbscan_model = HDBSCAN(
        min_cluster_size=max(2, min_cluster_size), min_samples=5,
        metric="euclidean", cluster_selection_method="eom",
        prediction_data=True,
    )

    # NOTE on token_pattern: Python's `re` module treats `\w` as unicode-aware
    # by default (re.UNICODE is implicit for str patterns in Py3), so umlauts
    # (ä/ö/ü/ß) are correctly preserved as word characters — no special
    # handling required. We additionally require >= 3 letters to filter noise.
    token_pattern = r"(?u)\b[^\W\d_]{3,}\b"

    def _build_model(vectorizer: CountVectorizer) -> BERTopic:
        return BERTopic(
            umap_model=umap_model,
            hdbscan_model=hdbscan_model,
            vectorizer_model=vectorizer,
            top_n_words=20,
            verbose=False,
            calculate_probabilities=False,
            nr_topics=nr_topics,
        )

    try:
        vectorizer = CountVectorizer(
            stop_words=german_stopwords, min_df=min_df, max_df=max_df,
            ngram_range=(1, 2), token_pattern=token_pattern,
        )
        topic_model = _build_model(vectorizer)
        topics, _ = topic_model.fit_transform(docs, embeddings)
    except Exception as e:
        log.warning(f"  [{concept}] Primary vectoriser failed ({e}); "
                    f"retrying with unconstrained vocabulary …")
        vectorizer = CountVectorizer(
            stop_words=german_stopwords, ngram_range=(1, 2),
            token_pattern=token_pattern,
        )
        topic_model = _build_model(vectorizer)
        topics, _ = topic_model.fit_transform(docs, embeddings)

    n_topics = len(set(topics))
    log.info(f"  [{concept}] Fitted {n_topics} topic(s) "
             f"({sum(1 for t in topics if t == -1)} outlier docs).")

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    with open(cache_path, "wb") as f:
        pickle.dump({"concept": concept, "model": topic_model, "topics": topics}, f)

    return topic_model, topics


# ══════════════════════════════════════════════════════════════════════════
#  STEP 6 — HUMAN-READABLE TOPIC LABELS
# ══════════════════════════════════════════════════════════════════════════

def load_topic_overrides(path: Path, log: logging.Logger) -> dict[str, dict[str, str]]:
    """Load manual topic-label overrides, e.g.:
        { "Evolution": { "0": "Fossile Belege", "1": "Selektionsmechanismen" } }
    Returns an empty dict (with a log note) if the file doesn't exist —
    overrides are entirely optional and layered on top of auto-labels.
    """
    if not path.exists():
        log.info(f"No topic-label override file at {path} (using auto-labels only).")
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        log.info(f"Loaded topic-label overrides for {len(data)} concept(s) from {path}.")
        return data
    except Exception as e:
        log.warning(f"Could not parse topic overrides at {path}: {e} — ignoring.")
        return {}


def build_topic_labels(
    concept: str, topic_model: BERTopic, overrides: dict[str, dict[str, str]],
) -> dict[int, str]:
    """Derive a human-readable label for every topic ID produced for a
    concept: manual override > auto keyword label > generic fallback.

    Auto labels join the top-3 keyword terms (Title-Cased) with " · ",
    e.g. "Fossil · Stammesgeschichte · Merkmal". Topic -1 (BERTopic's
    catch-all outlier bucket) is always labelled as an outlier bucket,
    matching the `is_outlier` flag exported per record.
    """
    concept_overrides = overrides.get(concept, {})
    labels: dict[int, str] = {}

    for topic_id in sorted(set(topic_model.topics_)):
        if topic_id == -1:
            labels[topic_id] = concept_overrides.get(str(topic_id), "Kein Thema (Ausreißer)")
            continue

        override = concept_overrides.get(str(topic_id))
        if override:
            labels[topic_id] = override
            continue

        terms = topic_model.get_topic(topic_id) or []
        top_words = [w.title() for w, _ in terms[:3] if w.strip()]
        labels[topic_id] = " · ".join(top_words) if top_words else f"Thema {topic_id}"

    return labels


# ══════════════════════════════════════════════════════════════════════════
#  STEP 7 — TOPIC × SUBJECT DISTRIBUTION DIAGNOSTICS (OPTIONAL)
# ══════════════════════════════════════════════════════════════════════════

def analyze_topic_subject_distribution(
    concept: str, meta_df: pd.DataFrame, topic_model: BERTopic,
    topic_labels: dict[int, str], out_dir: Path, log: logging.Logger,
) -> None:
    """Write diagnostic CSVs describing how topics distribute across school
    subjects (and vice versa), including per-row Shannon entropy. These are
    NOT consumed by the web app — they're analyst-facing sanity checks.
    """
    concept_dir = out_dir / concept
    concept_dir.mkdir(parents=True, exist_ok=True)

    work = meta_df.copy()
    work["subject_clean"] = work[COLUMN_MAP["subject"]].map(clean_subject)
    work["topic_name"] = work["bertopic_topic"].map(topic_labels)

    counts = work.groupby(["topic_name", "subject_clean"]).size().unstack(fill_value=0)
    total = counts.values.sum()
    if total == 0:
        log.warning(f"  [{concept}] No data for distribution analysis — skipping.")
        return

    topics_over_subjects = counts.div(counts.sum(axis=1), axis=0)
    topics_over_subjects["entropy"] = topics_over_subjects.apply(
        lambda row: entropy(row, base=2), axis=1)
    topics_over_subjects["topic_total"] = counts.sum(axis=1)
    topics_over_subjects["topic_proportion"] = topics_over_subjects["topic_total"] / total
    topics_over_subjects.round(4).to_csv(concept_dir / f"dist_topics_over_subjects_{concept}.csv")

    subjects_over_topics = counts.T.div(counts.T.sum(axis=1), axis=0)
    subjects_over_topics["entropy"] = subjects_over_topics.apply(
        lambda row: entropy(row, base=2), axis=1)
    subjects_over_topics["subject_total"] = counts.T.sum(axis=1)
    subjects_over_topics["subject_proportion"] = subjects_over_topics["subject_total"] / total
    subjects_over_topics.round(4).to_csv(concept_dir / f"dist_subjects_over_topics_{concept}.csv")

    log.info(f"  [{concept}] Saved topic/subject distribution diagnostics.")


# ══════════════════════════════════════════════════════════════════════════
#  STEP 8 — JSON EXPORT FOR THE WEB APP
# ══════════════════════════════════════════════════════════════════════════

def export_concept_json(
    concept: str,
    meta_df: pd.DataFrame,
    topics: list[int],
    umap2d: np.ndarray,
    umap3d: np.ndarray,
    topic_labels: dict[int, str],
    web_data_dir: Path,
    pretty: bool,
    log: logging.Logger,
    state_tracker: Counter,
) -> dict[str, Any]:
    """Write `data/<Concept>.json` in the exact schema the front-end expects,
    and return a manifest fragment summarising this concept (used to build
    the corpus-wide manifest.json without re-reading every file).
    """
    assert len(meta_df) == len(topics) == len(umap2d) == len(umap3d), (
        f"[{concept}] Length mismatch: meta={len(meta_df)} topics={len(topics)} "
        f"umap2d={len(umap2d)} umap3d={len(umap3d)}"
    )

    records: list[dict[str, Any]] = []
    subject_counter: Counter = Counter()
    state_counter: Counter = Counter()
    topic_counter: Counter = Counter()

    for i in range(len(meta_df)):
        row = meta_df.iloc[i]
        topic_id = int(topics[i])
        state = canonicalize_state(row[COLUMN_MAP["state"]], state_tracker)
        subject = clean_subject(row[COLUMN_MAP["subject"]])
        grade_band = derive_grade_band(row[COLUMN_MAP["grade"]])
        topic_label = topic_labels.get(topic_id, f"Thema {topic_id}")

        record = {
            "id": int(row["doc_id"]),
            "state": state,
            "subject": subject,
            "grade_band": grade_band,
            "topic": topic_label,
            "is_outlier": bool(topic_id == -1),
            "umap_2d": [round(float(umap2d[i, 0]), 4), round(float(umap2d[i, 1]), 4)],
            "umap_3d": [round(float(umap3d[i, 0]), 4), round(float(umap3d[i, 1]), 4),
                        round(float(umap3d[i, 2]), 4)],
            "excerpt": str(row[COLUMN_MAP["text"]]).strip(),
        }
        records.append(record)
        subject_counter[subject] += 1
        state_counter[state] += 1
        topic_counter[topic_label] += 1

    records.sort(key=lambda r: r["id"])

    web_data_dir.mkdir(parents=True, exist_ok=True)
    out_path = web_data_dir / f"{concept}.json"
    dump_kwargs = dict(ensure_ascii=False, indent=2) if pretty else dict(ensure_ascii=False)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(records, f, **dump_kwargs)
    log.info(f"  [{concept}] Wrote {len(records):,} records -> {out_path}")

    # Bounding boxes let the front-end pre-scale axes before data is fetched.
    def _bbox(coords: np.ndarray) -> list[list[float]]:
        return [[round(float(coords[:, d].min()), 4), round(float(coords[:, d].max()), 4)]
                for d in range(coords.shape[1])]

    return {
        "concept": concept,
        "n_docs": len(records),
        "n_outliers": sum(1 for r in records if r["is_outlier"]),
        "subjects": dict(sorted(subject_counter.items(), key=lambda kv: -kv[1])),
        "states": dict(sorted(state_counter.items(), key=lambda kv: -kv[1])),
        "topics": dict(sorted(topic_counter.items(), key=lambda kv: -kv[1])),
        "bbox_2d": _bbox(umap2d),
        "bbox_3d": _bbox(umap3d),
    }


def build_manifest(
    fragments: list[dict[str, Any]], csv_checksum: str,
    web_data_dir: Path, pretty: bool, log: logging.Logger,
) -> None:
    """Aggregate every concept's manifest fragment into a single
    `data/manifest.json`, used by the front-end to populate concept lists,
    filters and legends before/without downloading per-concept payloads.
    """
    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_csv_md5": csv_checksum,
        "embedding_model": EMBEDDING_MODEL_NAME,
        "random_seed": RANDOM_SEED,
        "concept_order": DEFAULT_CONCEPTS,
        "concepts": {frag["concept"]: frag for frag in fragments},
    }
    out_path = web_data_dir / "manifest.json"
    dump_kwargs = dict(ensure_ascii=False, indent=2) if pretty else dict(ensure_ascii=False)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, **dump_kwargs)
    log.info(f"Wrote manifest -> {out_path}")


# ══════════════════════════════════════════════════════════════════════════
#  PER-CONCEPT ORCHESTRATION
# ══════════════════════════════════════════════════════════════════════════

def process_concept(
    concept: str,
    df: pd.DataFrame,
    embeddings_all: np.ndarray,
    cfg: RunConfig,
    topic_overrides: dict[str, dict[str, str]],
    state_tracker: Counter,
    log: logging.Logger,
) -> Optional[dict[str, Any]]:
    """Run the full per-concept pipeline (slice -> topics -> UMAP -> export).
    Returns the manifest fragment on success, or None on failure (failures
    are logged with full tracebacks but do not abort the overall run).
    """
    meta_df = get_concept_documents(df, concept)
    n = len(meta_df)
    if n == 0:
        log.warning(f"[{concept}] No matching documents found — skipping.")
        return None
    log.info(f"[{concept}] {n:,} matching documents.")

    docs = meta_df[COLUMN_MAP["text"]].astype(str).tolist()
    embeddings = embeddings_all[meta_df["doc_id"].to_numpy()]

    topic_model, topics = fit_or_load_bertopic(
        concept, docs, embeddings, cfg.cache_dir, log,
        nr_topics=cfg.nr_topics, force=cfg.force_topics,
    )
    meta_df["bertopic_topic"] = topics

    umap2d = compute_or_load_umap(
        embeddings, cfg.cache_dir / concept / f"umap2d_{concept}__{embedding_model_slug()}.npy",
        n_components=2, log=log, force=cfg.force_umap,
    )
    umap3d = compute_or_load_umap(
        embeddings, cfg.cache_dir / concept / f"umap3d_{concept}__{embedding_model_slug()}.npy",
        n_components=3, log=log, force=cfg.force_umap,
    )

    topic_labels = build_topic_labels(concept, topic_model, topic_overrides)

    if not cfg.skip_stats:
        analyze_topic_subject_distribution(
            concept, meta_df, topic_model, topic_labels, cfg.out_dir, log)

    fragment = export_concept_json(
        concept, meta_df, topics, umap2d, umap3d, topic_labels,
        cfg.web_data_dir, cfg.pretty_json, log, state_tracker,
    )
    return fragment


# ══════════════════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════════════════

def main() -> None:
    cfg = parse_args()
    log = setup_logging(cfg.out_dir, cfg.log_level)
    warnings.filterwarnings("ignore")
    set_global_seed(RANDOM_SEED)

    log.info("=" * 78)
    log.info("  Evo-Buch Curriculum-Atlas — BERTopic Data Generation Pipeline")
    log.info("=" * 78)
    log.info(f"CSV:          {cfg.csv_path}")
    log.info(f"Web data dir: {cfg.web_data_dir}")
    log.info(f"Cache dir:    {cfg.cache_dir}")
    log.info(f"Out dir:      {cfg.out_dir}")
    log.info(f"Concepts:     {len(cfg.concepts)} -> {cfg.concepts}")

    if cfg.dry_run:
        log.info("[DRY RUN] Validating CSV only, no computation will be performed.")
        df = load_source_csv(cfg.csv_path, log)
        for concept in cfg.concepts:
            n = int((df[COLUMN_MAP["concept"]] == concept).sum())
            log.info(f"  {concept:<15s} {n:>6,} matching rows")
        log.info("[DRY RUN] Complete — exiting without writes.")
        return

    for d in (cfg.web_data_dir, cfg.cache_dir, cfg.out_dir):
        d.mkdir(parents=True, exist_ok=True)

    csv_checksum = md5_of_file(cfg.csv_path)
    log.info(f"Source CSV checksum (MD5): {csv_checksum}")

    df = load_source_csv(cfg.csv_path, log)
    topic_overrides = load_topic_overrides(cfg.topic_overrides_path, log)

    embeddings_all = compute_or_load_embeddings(
        df[COLUMN_MAP["text"]].astype(str).tolist(),
        cfg.cache_dir, log, force=cfg.force_embeddings,
    )

    state_tracker: Counter = Counter()
    fragments: list[dict[str, Any]] = []
    failures: list[str] = []

    for concept in tqdm(cfg.concepts, desc="Concepts", unit="concept"):
        log.info("-" * 78)
        log.info(f"CONCEPT: {concept}")
        log.info("-" * 78)
        try:
            fragment = process_concept(
                concept, df, embeddings_all, cfg,
                topic_overrides, state_tracker, log,
            )
            if fragment:
                fragments.append(fragment)
        except Exception:
            log.error(f"[{concept}] Pipeline FAILED:\n{traceback.format_exc()}")
            failures.append(concept)

    build_manifest(fragments, csv_checksum, cfg.web_data_dir, cfg.pretty_json, log)

    if state_tracker:
        unmapped_path = cfg.out_dir / "unmapped_states.txt"
        with open(unmapped_path, "w", encoding="utf-8") as f:
            for state, count in state_tracker.most_common():
                f.write(f"{count:>6}  {state}\n")
        log.warning(f"{len(state_tracker)} unmapped state value(s) logged -> {unmapped_path}")

    log.info("=" * 78)
    log.info(f"DONE. Succeeded: {len(fragments)}/{len(cfg.concepts)} concept(s).")
    if failures:
        log.warning(f"Failed concepts: {failures}")
    log.info("=" * 78)


if __name__ == "__main__":
    main()
