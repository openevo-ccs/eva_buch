from pathlib import Path


ROOT       = Path(__file__).parent
DATA_DIR   = ROOT / "data"

KW_DIR  = ROOT / "keyword_search" 
LDA_DIR  = ROOT / "lda_topic_modelling" 
TM_DIR = ROOT / "bertopic" 

KW_OUT = KW_DIR / "out"
LDA_OUT = LDA_DIR / "out"
TM_OUT = TM_DIR / "out"

KW_IN = KW_DIR / "in"
LDA_IN = LDA_DIR / "in"
TM_IN = TM_DIR / "in"

TM_CACHE = TM_DIR / "cache"

RESULT_PATH = KW_OUT / "results.csv"




