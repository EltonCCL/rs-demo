from __future__ import annotations

import argparse
import json
from collections import deque
from pathlib import Path
from typing import Any

import fitz


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records),
        encoding="utf-8",
    )


def rgb_pixmap(path: Path) -> fitz.Pixmap:
    pixmap = fitz.Pixmap(str(path))
    if pixmap.n != 3 or pixmap.alpha:
        pixmap = fitz.Pixmap(fitz.csRGB, pixmap)
    return pixmap


def foreground_mask(pixmap: fitz.Pixmap, white_threshold: int) -> bytearray:
    samples = pixmap.samples
    mask = bytearray(pixmap.width * pixmap.height)
    for index in range(0, len(samples), 3):
        r, g, b = samples[index], samples[index + 1], samples[index + 2]
        if min(r, g, b) < white_threshold:
            mask[index // 3] = 1
    return mask


def component_bbox(
    mask: bytearray,
    width: int,
    height: int,
    start_index: int,
    visited: bytearray,
) -> tuple[int, tuple[int, int, int, int]]:
    queue: deque[int] = deque([start_index])
    visited[start_index] = 1
    count = 0
    min_x = width
    min_y = height
    max_x = 0
    max_y = 0

    while queue:
        index = queue.popleft()
        count += 1
        x = index % width
        y = index // width
        min_x = min(min_x, x)
        min_y = min(min_y, y)
        max_x = max(max_x, x)
        max_y = max(max_y, y)

        for neighbor in (index - 1, index + 1, index - width, index + width):
            if neighbor < 0 or neighbor >= len(mask):
                continue
            if neighbor == index - 1 and x == 0:
                continue
            if neighbor == index + 1 and x == width - 1:
                continue
            if mask[neighbor] and not visited[neighbor]:
                visited[neighbor] = 1
                queue.append(neighbor)

    return count, (min_x, min_y, max_x + 1, max_y + 1)


def largest_foreground_bbox(
    pixmap: fitz.Pixmap,
    white_threshold: int,
    min_component_pixels: int,
) -> tuple[int, int, int, int] | None:
    mask = foreground_mask(pixmap, white_threshold)
    visited = bytearray(len(mask))
    best_count = 0
    best_bbox: tuple[int, int, int, int] | None = None

    for index, is_foreground in enumerate(mask):
        if not is_foreground or visited[index]:
            continue
        count, bbox = component_bbox(mask, pixmap.width, pixmap.height, index, visited)
        if count > best_count:
            best_count = count
            best_bbox = bbox

    if best_count < min_component_pixels:
        return None
    return best_bbox


def pad_bbox(
    bbox: tuple[int, int, int, int],
    width: int,
    height: int,
    padding: int,
) -> tuple[int, int, int, int]:
    x0, y0, x1, y1 = bbox
    return (
        max(0, x0 - padding),
        max(0, y0 - padding),
        min(width, x1 + padding),
        min(height, y1 + padding),
    )


def crop_image(
    source_path: Path,
    output_path: Path,
    white_threshold: int,
    padding: int,
    min_component_pixels: int,
) -> dict[str, Any]:
    pixmap = rgb_pixmap(source_path)
    bbox = largest_foreground_bbox(pixmap, white_threshold, min_component_pixels)
    if bbox is None:
        return {
            "source_path": str(source_path),
            "cropped_path": None,
            "status": "no_foreground",
            "source_width": pixmap.width,
            "source_height": pixmap.height,
        }

    padded = pad_bbox(bbox, pixmap.width, pixmap.height, padding)
    clip = fitz.IRect(*padded)
    cropped = fitz.Pixmap(pixmap, pixmap.width, pixmap.height, clip)
    if cropped.n != 3 or cropped.alpha:
        cropped = fitz.Pixmap(fitz.csRGB, cropped)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    cropped.save(output_path)

    return {
        "source_path": str(source_path),
        "cropped_path": str(output_path),
        "status": "cropped",
        "source_width": pixmap.width,
        "source_height": pixmap.height,
        "crop_bbox": list(padded),
        "crop_width": cropped.width,
        "crop_height": cropped.height,
    }


def output_path_for(source_path: Path, source_root: Path, output_dir: Path) -> Path:
    try:
        relative = source_path.relative_to(source_root)
    except ValueError:
        relative = Path(source_path.name)
    return output_dir / relative.with_suffix(".crop.png")


def crop_catalogue_images(
    records: list[dict[str, Any]],
    source_root: Path,
    output_dir: Path,
    white_threshold: int,
    padding: int,
    min_component_pixels: int,
) -> list[dict[str, Any]]:
    paths = sorted({record.get("product_image_path") for record in records if record.get("product_image_path")})
    crop_results: dict[str, dict[str, Any]] = {}

    for path_value in paths:
        source_path = Path(path_value)
        if not source_path.is_absolute():
            source_path = Path.cwd() / source_path
        output_path = output_path_for(source_path, source_root, output_dir)
        result = crop_image(
            source_path,
            output_path,
            white_threshold,
            padding,
            min_component_pixels,
        )
        crop_results[path_value] = result

    for record in records:
        result = crop_results.get(record.get("product_image_path"))
        if result and result.get("cropped_path"):
            record["cropped_product_image_path"] = result["cropped_path"]
        else:
            record["cropped_product_image_path"] = None

    return list(crop_results.values())


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Crop whitespace from extracted product images.")
    parser.add_argument(
        "--catalogue",
        type=Path,
        default=Path("data/extracted/product_parse_sample.jsonl"),
        help="Input product JSONL path.",
    )
    parser.add_argument(
        "--out-catalogue",
        type=Path,
        default=Path("data/extracted/product_parse_sample.jsonl"),
        help="Output product JSONL path with cropped image paths.",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("data/extracted/product_image_crops"),
        help="Output directory for cropped images.",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("data/extracted/product_image_crops_manifest.json"),
        help="Output JSON crop manifest.",
    )
    parser.add_argument(
        "--source-root",
        type=Path,
        default=Path("data/extracted/pymupdf_probe"),
        help="Root directory of extracted source images.",
    )
    parser.add_argument("--white-threshold", type=int, default=245)
    parser.add_argument("--padding", type=int, default=18)
    parser.add_argument("--min-component-pixels", type=int, default=250)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    records = load_jsonl(args.catalogue)
    results = crop_catalogue_images(
        records,
        args.source_root.resolve(),
        args.out_dir,
        args.white_threshold,
        args.padding,
        args.min_component_pixels,
    )
    write_jsonl(args.out_catalogue, records)
    args.manifest.write_text(json.dumps(results, indent=2), encoding="utf-8")

    cropped = sum(1 for result in results if result["status"] == "cropped")
    print(f"cropped={cropped} images={len(results)} catalogue={args.out_catalogue}")


if __name__ == "__main__":
    main()
