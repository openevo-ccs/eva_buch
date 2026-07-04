import pymupdf
from pathlib import Path


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
            txt_path.write_text(text, encoding="utf-8")
            print(f"OK  {relative}")
        except Exception as e:
            print(f"FAIL {relative}: {e}")

