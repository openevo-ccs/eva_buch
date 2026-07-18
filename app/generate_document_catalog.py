import json
import re
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parent.parent
DATA_ROOT = ROOT / "data" / "LP_DE_2026_1_txtfiles"
OUTPUT_PATH = ROOT / "app" / "data" / "document_catalog.json"

STATE_PATTERNS = [
    ("Bayern", "Bayern"),
    ("BaWü", "BaWü"),
    ("Bawü", "BaWü"),
    ("Berlin", "Berlin"),
    ("Bremen", "Bremen"),
    ("Hamburg", "Hamburg"),
    ("Hessen", "Hessen"),
    ("MeckPomm", "MeckPomm"),
    ("Meckpomm", "MeckPomm"),
    ("Niedersachsen", "Niedersachsen"),
    ("NRW", "NRW"),
    ("Nordrhein-Westfalen", "NRW"),
    ("Rheinland-Pfalz", "Rheinland-Pfalz"),
    ("Saarland", "Saarland"),
    ("Sachsen", "Sachsen"),
    ("Sachsen-Anhalt", "Sachsen-Anhalt"),
    ("Schleswig-Holstein", "Schleswig-Holstein"),
    ("Thüringen", "Thüringen"),
    ("Thueringen", "Thüringen"),
    ("KMK", "KMK"),
]


def infer_state(file_name: str) -> str:
    lowered = file_name.lower()
    for pattern, label in STATE_PATTERNS:
        if pattern.lower() in lowered:
            return label
    return "Unbekannt"


def infer_year(file_name: str) -> int | None:
    match = re.search(r"(20\d{2})", file_name)
    if match:
        return int(match.group(1))
    return None


def build_catalog() -> dict:
    documents = []
    for path in sorted(DATA_ROOT.rglob("*.txt")):
        relative_path = path.relative_to(DATA_ROOT).as_posix()
        subject = path.parent.name
        title = path.stem
        documents.append(
            {
                "title": title,
                "subject": subject,
                "state": infer_state(path.name),
                "year": infer_year(path.name),
                "path": relative_path,
            }
        )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "documents": documents,
    }


if __name__ == "__main__":
    catalog = build_catalog()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(catalog, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {len(catalog['documents'])} documents to {OUTPUT_PATH}")
