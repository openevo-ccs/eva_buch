#!/usr/bin/env python3
"""Standing German-language data-integrity check, motivated by the BERTopic
ASCII-stripping bug (METHODOLOGY.md §4.6): BERTopic silently dropped every
umlaut/ß from every topic label because `language` defaulted to "english",
and this went undetected because the bug produced *valid but wrong* ASCII
text -- not mangled bytes -- so a naive "does this decode as UTF-8" check
would have passed while the data was already wrong.

Two independent checks, because they catch different failure modes:

1. UTF-8 decode check on every tracked output file under docs/data/ and
   bertopic/src/data/ -- catches byte-level corruption (e.g. the font-
   encoding remap bug documented in METHODOLOGY.md §1).
2. Corpus-wide positive-presence check for a curated list of common German
   words containing umlauts/ß -- catches silent *character-stripping* bugs
   like §4.6, which produce perfectly valid UTF-8 that is simply missing
   the German-specific characters. A word expected to appear somewhere in
   this corpus (curriculum documents, topic labels, term lists) that is
   never found anywhere is a red flag worth a human look, not proof of a
   bug on its own -- some words legitimately might not appear in some file
   categories (e.g. LDA term lists are single words, so "Ausreißer" as a
   whole word won't appear there, only its stem).

Meant to be rerun cheaply after any future pipeline change, not just as a
one-time audit.

Usage:
    python scripts/verify_utf8_integrity.py
    python scripts/verify_utf8_integrity.py --dirs docs/data bertopic/src/data
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

DEFAULT_DIRS = ["docs/data", "bertopic/src/data"]
SCAN_EXTENSIONS = {".csv", ".json", ".txt"}

# Common German words containing umlauts/ß expected to appear *somewhere*
# across this corpus (curriculum text, topic labels, keyword-search terms).
# Not exhaustive -- a representative sample spanning the app's own concept
# list and everyday curriculum vocabulary.
EXPECTED_WORDS = [
    "Ausreißer", "Schülerinnen", "Zusammenhänge", "Bedürfnis", "Bedürfnisse",
    "Gefühl", "Gefühle", "Rationalität", "Glück", "Länder", "Änderung",
    "für", "über", "können", "müssen", "größer", "natürlich", "Fähigkeit",
    "Übung", "Verhältnis", "während", "Auswärtige", "Prüfung",
]


def iter_scan_files(dirs: list[str]) -> list[Path]:
    files: list[Path] = []
    for d in dirs:
        base = ROOT / d
        if not base.exists():
            print(f"[WARN] scan directory not found, skipping: {base}")
            continue
        for path in base.rglob("*"):
            if path.is_file() and path.suffix.lower() in SCAN_EXTENSIONS:
                files.append(path)
    return files


def check_utf8_decodable(files: list[Path]) -> list[Path]:
    """Return the subset of files that fail to decode as UTF-8."""
    failures = []
    for path in files:
        try:
            path.read_bytes().decode("utf-8")
        except UnicodeDecodeError as e:
            failures.append(path)
            print(f"[FAIL] {path.relative_to(ROOT)}: {e}")
    return failures


def check_expected_words(files: list[Path]) -> list[str]:
    """Return expected words never found in any scanned file's text."""
    found = set()
    for path in files:
        try:
            text = path.read_bytes().decode("utf-8")
        except UnicodeDecodeError:
            continue  # already reported by check_utf8_decodable
        for word in EXPECTED_WORDS:
            if word in found:
                continue
            if word in text:
                found.add(word)
    return [w for w in EXPECTED_WORDS if w not in found]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dirs", nargs="+", default=DEFAULT_DIRS,
                         help="Directories to scan (relative to repo root).")
    args = parser.parse_args()

    files = iter_scan_files(args.dirs)
    print(f"Scanning {len(files)} file(s) under {args.dirs}...")

    decode_failures = check_utf8_decodable(files)
    missing_words = check_expected_words(files)

    print()
    if decode_failures:
        print(f"[FAIL] {len(decode_failures)} file(s) failed UTF-8 decode.")
    else:
        print("[OK] All scanned files decode as valid UTF-8.")

    if missing_words:
        print(f"[WARN] {len(missing_words)} expected German word(s) never found anywhere: {missing_words}")
        print("       Not proof of a bug by itself -- but worth a human look if unexpected.")
    else:
        print(f"[OK] All {len(EXPECTED_WORDS)} curated German words found somewhere in the corpus.")

    if decode_failures:
        sys.exit(1)


if __name__ == "__main__":
    main()
