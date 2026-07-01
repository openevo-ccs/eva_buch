# ─────────────────────────────────────────────────────────────────────────────
# IMPORTS
# ─────────────────────────────────────────────────────
from pathlib import Path

import pandas as pd
import numpy as np
import pandas as pd
import pickle
import logging, warnings, sys

# ─────────────────────────────────────────────────────────────────────────────
# PATHS
# ─────────────────────────────────────────────────────────────────────────────

BASE_DIR    = Path("/Users/julia/MPI_EVA/github/eva_buch")
DATA_DIR    = BASE_DIR / "data" 
CACHE_DIR   = BASE_DIR / "cache" 
OUTPUT_DIR  = BASE_DIR / "out" 

CSV_PATH    = DATA_DIR / "results.csv"
SEED_PATH   = DATA_DIR / "eva_seed_list.py"

# DOCS_CACHE  = CACHE_DIR / "documents.pkl"
# EMBED_CACHE = CACHE_DIR / "embeddings.npy"
META_CACHE  = CACHE_DIR / "metadata.pkl"
TOPIC_CACHE = CACHE_DIR / "topic_model.pkl"
UMAP_CACHE  = CACHE_DIR / "umap3d.npy"

HTML_OUTPUT = OUTPUT_DIR / "eva_topic_explorer.html"
SEPARATOR = " | "



warnings.filterwarnings("ignore")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def safe_str(val) -> str:
    if val is None:
        return ""
    try:
        if pd.isna(val):
            return ""
    except (TypeError, ValueError):
        pass
    return str(val).strip()


def safe_float(val, default: float = 0.0) -> float:
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


def to_py_list(arr) -> list:
    """Convert any numpy/pandas array to a plain Python list of Python scalars."""
    return [v.item() if hasattr(v, "item") else v for v in arr]


def _hex_to_rgba(hex_color: str, alpha: float = 1.0) -> str:
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"

def hex_to_rgb(h):
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)

def to_list(arr):
    if isinstance(arr, (pd.Series, np.ndarray)):
        return [v.item() if hasattr(v, "item") else v for v in arr]
    return list(arr)

def split_departments(dept_str) -> list[str]:
    """Split a possibly multi-valued department string into a clean list."""
    if pd.isna(dept_str) or str(dept_str).strip() == "":
        return ["Unassigned"]
    return [d.strip() for d in str(dept_str).split(SEPARATOR) if d.strip()]

def load_keywords(keyword_path: Path) -> list[str]:
    try:
        with open(keyword_path, 'r') as file:
            keywords = file.readlines()
            keywords = [word.strip() for word in keywords]
            log.info(f"Loaded {len(keywords)} keywords")
    except Exception as e:
        log.error(f"Couldn't load keyords: {e}")
    return keywords