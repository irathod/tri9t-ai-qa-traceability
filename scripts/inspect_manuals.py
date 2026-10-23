
from pathlib import Path
import fitz

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"

PDF_FILES = [
    DATA_DIR / "ct200_manual.pdf",
    DATA_DIR / "ct200_manual_v2.pdf",
]


def inspect_pdf(pdf_path: Path) -> None:
    """Inspect a PDF and report basic text extraction statistics."""

    if not pdf_path.exists():
        print(f"[ERROR] File not found: {pdf_path}")
        return

    print(f"\n{'=' * 60}")
    print(f"File: {pdf_path.name}")

    try:
        with fitz.open(pdf_path) as pdf:
            print(f"Pages: {len(pdf)}")

            for page_number, page in enumerate(pdf, start=1):
                text = page.get_text("text").strip()
                words = len(text.split())

                print(
                    f"Page {page_number}: "
                    f"{words} words, "
                    f"{len(text)} characters"
                )

                if words < 10:
                    print("  Review this page for possible OCR.")

                if page_number <= 2:
                    print("\nText preview:")
                    print(text[:800] or "[No extractable text]")
                    print("-" * 40)

    except (OSError, RuntimeError, fitz.FileDataError) as exc:
        print(f"[ERROR] Could not inspect PDF: {exc}")


def main() -> None:
    for pdf_path in PDF_FILES:
        inspect_pdf(pdf_path)


if __name__ == "__main__":
    main()
