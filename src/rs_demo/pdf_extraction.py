from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import fitz


@dataclass(frozen=True)
class PdfExtractionConfig:
    pdf_path: Path
    output_dir: Path = Path("data/extracted/pymupdf_probe")
    max_pages: int = 5
    zoom: float = 2.0


class PdfExtractor:
    def extract(self, config: PdfExtractionConfig) -> list[dict[str, Any]]:
        return probe_pdf(config.pdf_path, config.output_dir, config.max_pages, config.zoom)


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
