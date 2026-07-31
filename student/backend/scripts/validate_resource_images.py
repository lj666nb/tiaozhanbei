"""Validate that every configured resource illustration is deployable."""

from __future__ import annotations

import json
from pathlib import Path


DATA_DIR = Path(__file__).resolve().parent.parent / "data"
CONFIG_PATH = DATA_DIR / "resource_image_config.json"
IMAGES_DIR = DATA_DIR / "generated_images"
PDF_SEED_PATH = DATA_DIR / "pdf_books_seed.json"
PDF_DIR = DATA_DIR / "pdfs"


def main() -> None:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    available = {path.stem for path in IMAGES_DIR.glob("*.svg")}
    missing = {
        resource_id: [image_hash for image_hash in hashes if image_hash not in available]
        for resource_id, hashes in config.items()
    }
    missing = {resource_id: hashes for resource_id, hashes in missing.items() if hashes}

    if missing:
        details = "; ".join(
            f"{resource_id}: {', '.join(hashes)}"
            for resource_id, hashes in sorted(missing.items())
        )
        raise SystemExit(f"Missing configured resource SVG files: {details}")

    pdf_seed = json.loads(PDF_SEED_PATH.read_text(encoding="utf-8"))
    missing_pdfs = []
    missing_covers = []
    for book in pdf_seed:
        filename = Path(str(book.get("filename", ""))).name
        cover = Path(str(book.get("cover", ""))).name if book.get("cover") else None
        if not filename or not (PDF_DIR / filename).is_file():
            missing_pdfs.append(filename or "<empty filename>")
        if cover and not (PDF_DIR / "covers" / cover).is_file():
            missing_covers.append(f"covers/{cover}")
    if missing_pdfs:
        raise SystemExit(f"Missing bundled PDF files: {', '.join(missing_pdfs)}")
    if missing_covers:
        print(f"Warning: Missing PDF cover images (will be generated at runtime): {', '.join(missing_covers)}")

    print(
        f"Validated {sum(map(len, config.values()))} configured resource SVG references "
        f"and {len(pdf_seed)} bundled PDF records"
    )


if __name__ == "__main__":
    main()
