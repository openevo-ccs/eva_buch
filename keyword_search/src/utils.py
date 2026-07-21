import pymupdf
from pathlib import Path


# Known font-encoding mis-mappings observed in specific source PDFs. Some
# curriculum PDFs embed a font subset with a broken/non-standard character
# table, causing pymupdf to extract the wrong Unicode code point for German
# special characters instead of the correct one. Discovered 2026-07-21 in
# "LP RheinPfalz Philosohpie Gym Sek2.pdf" (544x u-with-diaeresis -> Ÿ,
# 463x a-with-diaeresis -> Š, 138x o-with-diaeresis -> š, 42x sharp-s -> ã).
# None of these four characters appear correctly in German text, so
# remapping them unconditionally is safe for every other document too.
# See METHODOLOGY.md section 1.
FONT_ENCODING_REMAP = {
    "Ÿ": "ü",  # Ÿ -> ü
    "Š": "ä",  # Š -> ä
    "š": "ö",  # š -> ö
    "ã": "ß",  # ã -> ß
}


def remap_font_encoding_artifacts(text: str) -> str:
    """Fix known font-encoding mis-mappings (FONT_ENCODING_REMAP) in text
    extracted from a PDF, before any other cleaning/normalisation runs.
    """
    for wrong, right in FONT_ENCODING_REMAP.items():
        text = text.replace(wrong, right)
    return text


def pdf_dir_to_txt(input_dir: str | Path, output_dir: str | Path) -> None:
    """
    Mirrors a directory of PDFs into a directory of .txt files,
    preserving subdirectory structure.

    Args:
        input_dir:  root folder containing subfolders with PDFs
        output_dir: root folder where mirrored txt structure will be created
    """
    input_dir  = Path(input_dir)
    output_dir = Path(output_dir)

    for pdf_path in input_dir.rglob("*.pdf"):
        relative = pdf_path.relative_to(input_dir)
        txt_path = output_dir / relative.with_suffix(".txt")
        txt_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            with pymupdf.open(pdf_path) as pdf:
                text = "\n".join(page.get_text() for page in pdf)
            text = remap_font_encoding_artifacts(text)
            txt_path.write_text(text, encoding="utf-8")
            print(f"OK  {relative}")
        except Exception as e:
            print(f"FAIL {relative}: {e}")

