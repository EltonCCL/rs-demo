from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import fitz


def clean_snippet(text: str, limit: int = 700) -> str:
    compact = " ".join(text.split())
    return compact[:limit]


def write_embedded_images(page: fitz.Page, page_dir: Path) -> list[dict[str, Any]]:
    image_rows: list[dict[str, Any]] = []

    for image_index, image in enumerate(page.get_images(full=True), start=1):
        xref = image[0]
        extracted = page.parent.extract_image(xref)
        extension = extracted.get("ext", "bin")
        image_path = page_dir / f"embedded_image_{image_index:02d}.{extension}"
        image_path.write_bytes(extracted["image"])

        image_rows.append(
            {
                "image_index": image_index,
                "xref": xref,
                "width": extracted.get("width"),
                "height": extracted.get("height"),
                "colorspace": extracted.get("colorspace"),
                "extension": extension,
                "path": str(image_path),
            }
        )

    return image_rows


def render_page(page: fitz.Page, page_dir: Path, zoom: float) -> Path:
    matrix = fitz.Matrix(zoom, zoom)
    pixmap = page.get_pixmap(matrix=matrix, alpha=False)
    image_path = page_dir / "page_render.png"
    pixmap.save(image_path)
    return image_path


def probe_pdf(pdf_path: Path, output_dir: Path, max_pages: int, zoom: float) -> list[dict[str, Any]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []

    with fitz.open(pdf_path) as document:
        page_count = min(document.page_count, max_pages)

        for page_number in range(page_count):
            page = document.load_page(page_number)
            page_dir = output_dir / f"page_{page_number + 1:04d}"
            page_dir.mkdir(parents=True, exist_ok=True)

            text = page.get_text("text")
            text_path = page_dir / "text.txt"
            text_path.write_text(text, encoding="utf-8")

            rendered_path = render_page(page, page_dir, zoom)
            embedded_images = write_embedded_images(page, page_dir)

            rows.append(
                {
                    "page": page_number + 1,
                    "text_chars": len(text),
                    "text_snippet": clean_snippet(text),
                    "embedded_image_count": len(embedded_images),
                    "embedded_images": embedded_images,
                    "text_path": str(text_path),
                    "rendered_page_path": str(rendered_path),
                }
            )

    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    return rows


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Probe PDF text and image extraction with PyMuPDF.")
    parser.add_argument("pdf", type=Path, help="Path to the PDF to inspect.")
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("data/extracted/pymupdf_probe"),
        help="Directory for rendered pages, extracted images, and manifest.",
    )
    parser.add_argument("--max-pages", type=int, default=5, help="Maximum pages to inspect.")
    parser.add_argument("--zoom", type=float, default=2.0, help="Page render zoom factor.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rows = probe_pdf(args.pdf, args.out_dir, args.max_pages, args.zoom)

    for row in rows:
        print(
            f"page={row['page']} "
            f"text_chars={row['text_chars']} "
            f"embedded_images={row['embedded_image_count']}"
        )
        if row["text_snippet"]:
            print(f"  text: {row['text_snippet']}")
        print(f"  render: {row['rendered_page_path']}")

    print(f"\nManifest written to {args.out_dir / 'manifest.json'}")


if __name__ == "__main__":
    main()
