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

UMAP_CACHE_ALL  = CACHE_DIR / "umap2d_all.npy"
EMBED_CACHE_ALL = CACHE_DIR / "embeddings_all.npy"

HTML_OUTPUT = OUTPUT_DIR / "eva_topic_explorer.html"
SEPARATOR = " | "

for d in [OUTPUT_DIR, CACHE_DIR]:
    d.mkdir(parents=True, exist_ok=True)

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

def load_keywords(keyword_path: Path) -> list[str]:
    try:
        with open(keyword_path, 'r') as file:
            keywords = file.readlines()
            keywords = [word.strip() for word in keywords]
            log.info(f"Loaded {len(keywords)} keywords")
    except Exception as e:
        log.error(f"Couldn't load keyords: {e}")
    return keywords

def load_umap_all():
    if UMAP_CACHE_ALL.exists():
        log.info("Loading 2-D UMAP from cache …")
        coords = np.load(UMAP_CACHE_ALL)
        log.info(f"  Loaded coords: shape {coords.shape}")
        return coords
    
def load_embeddings_all():
    
    if EMBED_CACHE_ALL.exists():
        log.info("Loading embeddings from cache …")
        embeddings = np.load(EMBED_CACHE_ALL)
        log.info(f"  Loaded embeddings: shape {embeddings.shape}")
        return embeddings
