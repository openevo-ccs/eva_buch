# ─────────────────────────────────────────────────────────────────────────────
# IMPORTS
# ─────────────────────────────────────────────────────────────────────────────
import zipfile
import os
import pandas as pd
import re
import unicodedata
import sys
from pathlib import Path
import pymupdf

sys.path.append(str(Path(__file__).parent.parent.parent))
from config import KW_IN, KW_OUT as OUT_DIR, DATA_DIR, RESULT_PATH as OUT_PATH
from utils import pdf_dir_to_txt, remap_font_encoding_artifacts

print("All libraries successfully imported!")

# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────────────────────────────────────
KEYWORD_PATH = KW_IN / "keywords.txt"   # one concept per line, comma-separated variants
ZIP_PATH     = DATA_DIR / "LP_DE2026_1.zip"
EXTRACT_TO   = DATA_DIR / "LP_DE_2026_1/"

# Number of words before and after a match to include in the excerpt
CONTEXT_SIZE = 30

# Height in points to clip from page top/bottom (removes headers/footers).
# 72 pt = 1 inch at standard PDF resolution.
HEADER_HEIGHT = 72
FOOTER_HEIGHT = 72

# German grade-level labels checked before falling back to numeric patterns
GRADE_LEVELS = [
    "Sekundarstufe", "Sek1", "Sek2", "Sek1,2", "SekII",
    "Sek 1", "Sek 2", "Studienstufe",
]

# School-type labels checked before falling back to suffix matching
SCHOOL_TYPES = ["Gym", "Gymnasium", "GemS", "Regionale Schule"]

# State name normalisations applied during metadata extraction
STATE_ALIASES = {
    "BerlinBB":   "Berlin",
    "RheinPfalz": "Rheinland-Pfalz",
}

# Unicode characters treated as hyphens during text normalisation
DASH_CHARS = [
    "\u002d",  # hyphen-minus
    "\u2010",  # hyphen
    "\u2011",  # non-breaking hyphen
    "\u2012",  # figure dash
    "\u2013",  # en dash
    "\u2014",  # em dash
    "\u2015",  # horizontal bar
    "\u2212",  # minus sign
    "\u00AD",  # soft hyphen
]


# ─────────────────────────────────────────────────────────────────────────────
# STEP 1 — EXTRACT ZIP
# ─────────────────────────────────────────────────────────────────────────────

def extract_zip(zip_path: Path, extract_to: Path | None = None) -> Path:
    """
    Extract a zip archive to a target directory.

    Args:
        zip_path:   Path to the zip file.
        extract_to: Directory to extract into. Defaults to the zip file's
                    parent directory if not provided.

    Returns:
        Path to the extraction directory.
    """
    if extract_to is None:
        extract_to = Path(zip_path).parent
    extract_to = Path(extract_to)
    extract_to.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(zip_path, "r") as zip_ref:
        zip_ref.extractall(extract_to)

    print(f"Extracted {zip_path} → {extract_to}")
    return extract_to


# ─────────────────────────────────────────────────────────────────────────────
# STEP 2 — METADATA EXTRACTION FROM FILENAME
# ─────────────────────────────────────────────────────────────────────────────

def extract_grade(text: str) -> str | None:
    """
    Extract a grade level from a filename string.

    Checks for known German grade-level labels first (e.g. 'Sekundarstufe',
    'Sek1'), then falls back to a regex that matches numeric grade ranges
    (e.g. '5-10', '7,8') while excluding four-digit years.

    Args:
        text: Filename or path component to search.

    Returns:
        Matched grade label or numeric range, or None if not found.
    """
    matched = [level for level in GRADE_LEVELS if level in text]
    if matched:
        return matched[0]

    # Match numeric grades (1–3 digits, optionally with dash/comma separators),
    # explicitly excluding four-digit year tokens
    pattern = r"\b(?!(?:\d{4}\b))(\d{1,3}(?:[-,]\d{1,3})*)\b"
    matches = re.findall(pattern, text)
    if matches:
        return matches[0]

    return None


def extract_school_type(text: str) -> str | None:
    """
    Extract a school type from a filename string.

    Checks for known school-type labels first, then falls back to any
    token containing the suffix 'schule' (e.g. 'Realschule', 'Hauptschule').

    Args:
        text: Filename or path component to search.

    Returns:
        Matched school type string, or None if not found.
    """
    matched = [st for st in SCHOOL_TYPES if st in text]
    if matched:
        return matched[0]

    # Fallback: any whitespace-delimited token containing 'schule'
    matched = [word for word in text.split() if "schule" in word]
    if matched:
        return matched[0]

    return None


def extract_year(text: str) -> str | None:
    """
    Extract a four-digit publication year from a filename string.

    Matches years in the range 1900–2099.

    Args:
        text: Filename or path component to search.

    Returns:
        First matched year as a string, or None if not found.
    """
    pattern = r"\b(19\d{2}|20\d{2})\b"
    years = re.findall(pattern, text)
    return years[0] if years else None


def get_meta(filename: str) -> dict | bool:
    """
    Extract structured metadata from a curriculum PDF filename.

    Filenames are expected to follow the convention:
      <prefix> <state> <school_type> <grade> <year> ...
    KMK documents are treated as having no specific state.

    Args:
        filename: Bare filename (not a full path).

    Returns:
        Dict with keys: file, state, school type, grade, year.
        Returns False for hidden files (starting with '.').
    """
    if filename.startswith("."):
        return False

    parts = filename.split()
    if parts[0] == "KMK":
        state = "None"
    else:
        state = parts[1]
        state = STATE_ALIASES.get(state, state)

    return {
        "file":        filename,
        "state":       state,
        "school type": extract_school_type(filename),
        "grade":       extract_grade(filename),
        "year":        extract_year(filename),
    }


# ─────────────────────────────────────────────────────────────────────────────
# STEP 3 — TEXT NORMALISATION & CLEANING
# ─────────────────────────────────────────────────────────────────────────────

def normalize_text(text: str) -> str:
    """
    Normalise Unicode and standardise dash/hyphen characters in raw PDF text.

    Replaces all Unicode dash variants with a plain ASCII hyphen-minus, then
    applies NFKC normalisation to resolve ligatures, compatibility characters,
    and other Unicode quirks introduced by PDF text extraction.

    Args:
        text: Raw text as extracted from a PDF page.

    Returns:
        Normalised text string.
    """
    text = remap_font_encoding_artifacts(text)
    for char in DASH_CHARS:
        text = text.replace(char, "-")
    return unicodedata.normalize("NFKC", text)


def clean_hyphenated_text(text: str) -> str:
    """
    Clean extracted PDF text for use as a search excerpt.

    Removes end-of-line hyphenation, numeric artefacts, repeated dots
    (e.g. table-of-contents leaders), non-German special characters,
    and excess whitespace.

    Args:
        text: Normalised text extracted from a PDF.

    Returns:
        Cleaned text suitable for keyword matching and display.
    """
    # Rejoin words split by end-of-line hyphenation
    text = re.sub(r"-\s*\n\s*", "", text)
    # Remove standalone numbers and numbering artefacts (e.g. "1.2.3.")
    text = re.sub(r"\b\d+(\.\d+)*\.?(?=\s|$)", "", text)
    # Remove repeated-dot artefacts (table of contents leaders)
    text = re.sub(r"\.(\s*\.){3,}", "", text)

    # Defensive check added 2026-07-21: report (don't silently drop) any
    # alphabetic character the whitelist below is about to strip. A real
    # letter being removed here is the signature of an unhandled PDF
    # font-encoding issue (see METHODOLOGY.md section 1) rather than
    # routine punctuation/symbol noise, which this filter also strips
    # constantly and harmlessly.
    stripped_letters = {
        ch for ch in text
        if ch.isalpha() and not re.match(r"[a-zA-ZäöüÄÖÜßéèêëçñ]", ch)
    }
    if stripped_letters:
        print(f"  WARNING: clean_hyphenated_text() is stripping unexpected "
              f"letter(s) {sorted(stripped_letters)!r} -- possible unhandled "
              f"font-encoding issue in the source PDF (see METHODOLOGY.md "
              f"section 1 for a known example).")

    # Remove characters outside the expected German/Latin alphabet
    text = re.sub(r"[^a-zA-ZäöüÄÖÜßéèêëçñ\s,.;:/-]", "", text)
    # Collapse line breaks to single spaces
    text = re.sub(r"\s*\n\s*", " ", text)
    # Collapse multiple spaces
    text = re.sub(r"\s+", " ", text).strip()
    return text


# ─────────────────────────────────────────────────────────────────────────────
# STEP 4 — KEYWORD SEARCH IN TEXT
# ─────────────────────────────────────────────────────────────────────────────

def get_word_context(text: str, start_index: int, context_size: int = 10) -> str | None:
    """
    Extract a word-level context window around a character-level match position.

    Converts the character offset of a regex match into a word index, then
    returns the surrounding words as a joined string.

    Args:
        text:         The full text in which the match was found.
        start_index:  Character offset of the match start (from re.Match.start()).
        context_size: Number of words to include before and after the match.

    Returns:
        Context string, or None if the match position cannot be located.
    """
    words      = text.split()
    char_count = 0
    word_index = -1

    for i, word in enumerate(words):
        # Account for the space following each word (except the last)
        word_len = len(word) + (1 if i < len(words) - 1 else 0)
        if char_count <= start_index < char_count + word_len:
            word_index = i
            break
        char_count += word_len

    if word_index == -1:
        return None

    start_word = max(0, word_index - context_size)
    end_word   = min(len(words), word_index + context_size + 1)
    return " ".join(words[start_word:end_word]).strip()


def search_text_for_term(
    text:         str,
    lemma:        str,
    term:         str,
    context_size: int = 10,
) -> list[dict]:
    """
    Search a cleaned text string for a single keyword and return match excerpts.

    Matching is case-insensitive for all terms except 'Gen' (which is
    case-sensitive to avoid matching common words like 'gegen').

    Args:
        text:         Full document text to search (will be cleaned internally).
        lemma:        The canonical concept label (used as 'search_term' in output).
        term:         The specific surface form to search for.
        context_size: Number of words before and after the match for the excerpt.

    Returns:
        List of dicts, each containing: search_term, match_term,
        text_excerpt, excerpt_length.
    """
    text    = clean_hyphenated_text(text)
    results = []
    pattern = r"\b" + re.escape(term) + r"\b"

    # 'Gen' is matched case-sensitively to avoid false positives
    flags   = 0 if term == "Gen" else re.IGNORECASE
    matches = re.finditer(pattern, text, flags)

    for match in matches:
        excerpt = get_word_context(text, match.start(), context_size)
        if excerpt:
            results.append({
                "search_term":    lemma,
                "match_term":     term,
                "text_excerpt":   excerpt,
                "excerpt_length": len(excerpt.split()),
            })
        else:
            print(f"  Warning: could not create excerpt for match at position {match.start()}")

    return results


# ─────────────────────────────────────────────────────────────────────────────
# STEP 5 — SEARCH A SINGLE PDF
# ─────────────────────────────────────────────────────────────────────────────

def search_pdf_for_terms(
    pdf_path:      str | Path,
    term_dict:     dict[str, list[str]],
    context_size:  int = 10,
    header_height: int = 72,
    footer_height: int = 72,
) -> list[dict]:
    """
    Extract text from a PDF and search it for all terms in a concept dictionary.

    Text is extracted page by page with header/footer regions clipped, then
    concatenated into a single document string before searching. Landscape
    pages are clipped on the left/right sides instead of top/bottom.

    Args:
        pdf_path:      Path to the PDF file.
        term_dict:     Dict mapping concept lemma → list of surface-form variants.
        context_size:  Number of words before/after each match for the excerpt.
        header_height: Points to clip from the top (portrait) or left (landscape).
        footer_height: Points to clip from the bottom (portrait) or right (landscape).

    Returns:
        List of match dicts, each containing search_term, match_term,
        text_excerpt, excerpt_length, and all metadata fields from get_meta().
    """
    doc      = pymupdf.open(pdf_path)
    meta     = get_meta(os.path.basename(pdf_path))
    results  = []
    document = ""

    # ── Concatenate page text, clipping header/footer regions ────────────────
    for page_num in range(len(doc)):
        page = doc[page_num]
        rect = page.rect

        if rect.width > rect.height:
            # Landscape: clip left and right margins instead
            content_rect = pymupdf.Rect(
                rect.x0 + header_height,
                rect.y0,
                rect.x1 - footer_height,
                rect.y1,
            )
        else:
            # Portrait: clip top and bottom margins
            content_rect = pymupdf.Rect(
                rect.x0,
                rect.y0 + header_height,
                rect.x1,
                rect.y1 - footer_height,
            )

        text      = page.get_text(clip=content_rect)
        document += normalize_text(text)

    # ── Search the full document text for each term variant ──────────────────
    for lemma, terms in term_dict.items():
        for term in terms:
            if term:
                matches = search_text_for_term(document, lemma, term, context_size)
                for match in matches:
                    match.update(meta)
                    results.append(match)

    return results


# ─────────────────────────────────────────────────────────────────────────────
# STEP 6 — SEARCH ALL PDFs IN A DIRECTORY
# ─────────────────────────────────────────────────────────────────────────────

def search_pdfs_for_terms(
    folder_path:   str | Path,
    term_dict:     dict[str, list[str]],
    context_size:  int = 10,
    header_height: int = 72,
    footer_height: int = 72,
) -> pd.DataFrame:
    """
    Recursively search all PDFs in a directory tree for a set of keywords.

    Skips any subdirectory named 'test'. The subject area is inferred from
    the immediate parent directory name of each PDF.

    Args:
        folder_path:   Root directory to search recursively.
        term_dict:     Dict mapping concept lemma → list of surface-form variants.
        context_size:  Number of words before/after each match for the excerpt.
        header_height: Points to clip from the top (portrait) or left (landscape).
        footer_height: Points to clip from the bottom (portrait) or right (landscape).

    Returns:
        DataFrame of all matches across all PDFs, with one row per match.
    """
    all_results = []
    print(f"{len(term_dict)} search concept(s)")

    for root, dirs, files in os.walk(folder_path):
        subject = os.path.basename(root)
        print(f"  Searching in '{subject}' …")

        if subject == "test":
            continue

        for filename in files:
            if not filename.endswith(".pdf"):
                continue
            pdf_path = os.path.join(root, filename)
            results  = search_pdf_for_terms(pdf_path, term_dict, context_size, header_height, footer_height)
            for result in results:
                result["subject"] = subject
            all_results.extend(results)

    return pd.DataFrame(all_results)


# ─────────────────────────────────────────────────────────────────────────────
# STEP 7 — EXECUTE SEARCH
# ─────────────────────────────────────────────────────────────────────────────

def load_concept_dict(keyword_path: Path) -> dict[str, list[str]]:
    """
    Parse a keyword file into a concept dictionary.

    Each line should contain a comma-separated list where the first token is
    the canonical lemma and the remaining tokens are surface-form variants:
      Nachhaltigkeit, Nachhaltigkeit, nachhaltig, Nachhaltigkeits

    Blank lines are ignored.

    Args:
        keyword_path: Path to the plain-text keyword file.

    Returns:
        Dict mapping lemma → list of all variants (including the lemma itself).
    """
    with open(keyword_path, "r") as f:
        lines = [line.strip() for line in f if line.strip()]
    return {
        line.split(",")[0].strip(): [item.strip() for item in line.split(",")]
        for line in lines
    }


def execute_search(
    basepath:      Path,
    keyword_path:  Path,
    out_path:      Path,
    context_size:  int = 10,
    search_term:   str | None = None,
    header_height: int = 72,
    footer_height: int = 72,
) -> pd.DataFrame:
    """
    Load keywords, run the PDF search, and save results to CSV.

    If `search_term` is provided, only that concept is searched; otherwise
    all concepts in the keyword file are searched.

    Args:
        basepath:      Root directory containing subject subdirectories with PDFs.
        keyword_path:  Path to the keyword file.
        out_path:      Path where the results CSV will be written.
        context_size:  Number of words before/after each match for the excerpt.
        search_term:   Optional concept lemma to restrict the search to.
        header_height: Points to clip from page top (portrait) or left (landscape).
        footer_height: Points to clip from page bottom (portrait) or right (landscape).

    Returns:
        DataFrame of all matches, also saved to `out_path`.
    """
    concept_dict = load_concept_dict(keyword_path)

    if search_term is None:
        print("No search term selected — searching for all concepts.")
        term_dict = concept_dict
    else:
        print(f"Searching for concept: '{search_term}'")
        term_dict = {search_term: concept_dict[search_term]}

    result_df = search_pdfs_for_terms(basepath, term_dict, context_size, header_height, footer_height)

    try:
        result_df.to_csv(out_path, index=False)
        print(f"Results saved to {out_path}")
    except Exception as e:
        print(f"Could not save results: {e}")

    return result_df


# ─────────────────────────────────────────────────────────────────────────────
# STEP 8 — DESCRIPTIVE STATISTICS
# ─────────────────────────────────────────────────────────────────────────────

def count_words(folder_path: str | Path) -> pd.DataFrame:
    """
    Count the total number of words per PDF across a directory tree.

    Walks the directory recursively and counts whitespace-delimited tokens
    on every page of every PDF. Metadata is extracted from each filename.
    Results are saved to OUT_DIR/doc_word_counts.csv.

    Args:
        folder_path: Root directory to walk.

    Returns:
        DataFrame with one row per PDF and columns: file, state, school type,
        grade, year, subject, word_count.
    """
    word_counts = []

    for root, dirs, files in os.walk(folder_path):
        for filename in files:
            if not filename.endswith(".pdf"):
                continue

            pdf_path   = os.path.join(root, filename)
            doc        = pymupdf.open(pdf_path)
            word_count = sum(
                len(doc.load_page(p).get_text("text").split())
                for p in range(len(doc))
            )

            row            = get_meta(filename)
            row["subject"] = os.path.basename(root)
            row["word_count"] = word_count
            word_counts.append(row)

    df_counts = pd.DataFrame(word_counts)
    df_counts.to_csv(OUT_DIR / "doc_word_counts.csv", index=False)
    return df_counts


def make_pivot(df: pd.DataFrame, column_a: str, column_b: str) -> pd.DataFrame:
    """
    Build a cross-tabulation of document counts between two metadata columns.

    Deduplicates on (file, state, subject) before pivoting so that each
    document is counted only once. Adds row and column totals.
    Saves the result to OUT_DIR/state_subject_count_matrix.csv.

    Args:
        df:       DataFrame containing at least 'file', 'state', and 'subject'.
        column_a: Row dimension for the pivot (e.g. 'state').
        column_b: Column dimension for the pivot (e.g. 'subject').

    Returns:
        Pivot DataFrame with a 'Total' row and column appended.
    """
    deduped = df[["file", "state", "subject"]].drop_duplicates()
    matrix  = deduped.pivot_table(index=column_a, columns=column_b, aggfunc="size", fill_value=0)
    matrix["Total"]        = matrix.sum(axis=1)
    matrix.loc["Total"]    = matrix.sum(axis=0)
    matrix.to_csv(OUT_DIR / "state_subject_count_matrix.csv")
    return matrix


def count_terms(df: pd.DataFrame, keyword_path: Path) -> pd.DataFrame:
    """
    Count how often each search concept appears in the results.

    Concepts with zero matches are included in the output (count = 0) so
    that absent concepts are visible. Saves to OUT_DIR/term_count.csv.

    Args:
        df:           Results DataFrame with a 'search_term' column.
        keyword_path: Path to the keyword file (to identify zero-match concepts).

    Returns:
        DataFrame with columns: Search concept, Count.
    """
    count_dict   = df["search_term"].value_counts().to_dict()
    concept_dict = load_concept_dict(keyword_path)

    # Ensure all concepts appear even if they had no matches
    for k in concept_dict:
        if k not in count_dict:
            count_dict[k] = 0

    df_counts = pd.DataFrame(list(count_dict.items()), columns=["Search concept", "Count"])
    df_counts.to_csv(OUT_DIR / "term_count.csv")
    return df_counts


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    """
    Run the full keyword search pipeline.

    Pipeline steps:
      1. Extract the source zip archive
      2. Convert PDFs to plain-text files (for downstream use)
      3. Search all PDFs for all keywords and save match excerpts
      4. Build a state × subject document count matrix
      5. Count matches per search concept
      6. Count words per document
    """
    # Step 1 — Extract zip
    data_path = extract_zip(ZIP_PATH, EXTRACT_TO)

    # Step 2 — Convert PDFs to txt (for downstream pipelines)
    pdf_dir_to_txt(data_path, DATA_DIR / "LP_DE_2026_1_txtfiles")

    # Step 3 — Keyword search
    result_df = execute_search(
        basepath=data_path,
        keyword_path=KEYWORD_PATH,
        out_path=OUT_PATH,
        context_size=CONTEXT_SIZE,
        header_height=HEADER_HEIGHT,
        footer_height=FOOTER_HEIGHT,
    )

    # Step 4 — State × subject matrix
    pivot_df = make_pivot(result_df, "state", "subject")

    # Step 5 — Term match counts
    term_count_df = count_terms(result_df, KEYWORD_PATH)

    # Step 6 — Word counts per document
    word_counts = count_words(data_path)


if __name__ == "__main__":
    main()