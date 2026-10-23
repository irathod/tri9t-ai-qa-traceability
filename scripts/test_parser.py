
from pathlib import Path
import sys
import json

# Add the project root to Python's module search path.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.services.pdf_parser import parse_pdf, print_tree

DATA_DIR = ROOT / "data"


def main() -> None:
    for filename in ("ct200_manual.pdf", "ct200_manual_v2.pdf"):
        pdf_path = DATA_DIR / filename

        print(f"\n{'=' * 60}")
        print(f"Parsing: {filename}")

        tree = parse_pdf(pdf_path)
        print_tree(tree)

        output_path = DATA_DIR / f"{pdf_path.stem}_parsed.json"
        output_path.write_text(
            json.dumps(tree, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        print(f"\nSaved parsed tree: {output_path}")


if __name__ == "__main__":
    main()
