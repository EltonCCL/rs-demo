from __future__ import annotations

import argparse
import json
import re
import unicodedata
from pathlib import Path
from typing import Any


COUNTRIES = {
    "Australia",
    "Canada",
    "England",
    "Finland",
    "France",
    "Germany",
    "India",
    "Ireland",
    "Japan",
    "Scotland",
    "Sweden",
    "Taiwan",
    "USA",
    "Wales",
}

STYLE_PREFIXES = (
    "SINGLE MALT",
    "BLENDED MALT",
    "BLENDED WHISKY",
    "BLEND",
    "BLENDED CANADIAN RYE",
    "BOURBON",
    "CANADIAN RYE",
    "COLORADO WHISKEY",
    "DOUBLE BARREL WHISKEY",
    "RYE",
    "TENNESSEE WHISKEY",
    "IRISH WHISKEY",
    "IRISH POT STILL WHISKEY",
    "KENTUCKY WHISKEY",
    "GRAIN WHISKY",
    "MALT",
    "MIXED GRAIN WHISKEY",
    "NEW MAKE",
    "OREGON WHISKEY",
    "POTEEN",
    "PURE POT STILL",
    "CORN WHISKEY",
    "SINGLE GRAIN",
    "WHEAT WHISKEY",
)

NOISE_LINES = {
    "W H I S K E Y S",
    "G R E A T",
}


def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    replacements = {
        "\ufb01": "fi",
        "\ufb02": "fl",
        "▶": "",
        "◀": "",
    }
    for source, target in replacements.items():
        text = text.replace(source, target)
    return text


def clean_line(line: str) -> str:
    line = normalize_text(line)
    line = re.sub(r"\s+", " ", line).strip()
    return line


def is_noise_line(line: str) -> bool:
    if not line:
        return True
    if line in NOISE_LINES:
        return True
    if re.fullmatch(r"\d+", line):
        return True
    if re.fullmatch(r"[A-Z]", line):
        return True
    return False


def clean_lines(text: str) -> list[str]:
    return [line for line in (clean_line(line) for line in text.splitlines()) if not is_noise_line(line)]


def is_upperish(line: str) -> bool:
    letters = [character for character in line if character.isalpha()]
    if not letters:
        return False
    upper_count = sum(1 for character in letters if character.isupper())
    return upper_count / len(letters) >= 0.75


def is_spec_line(line: str) -> bool:
    if not is_upperish(line):
        return False

    upper = line.upper()
    if upper == "MALT":
        return True
    if upper.startswith("MALT "):
        return bool(re.fullmatch(r"MALT\s+\d+(?:\.\d+)?% ABV", upper))

    return any(
        upper == style or upper.startswith(f"{style}:") or upper.startswith(f"{style} ")
        for style in STYLE_PREFIXES
        if style != "MALT"
    )


def spec_span(lines: list[str], index: int) -> tuple[str, int]:
    spec_lines = [lines[index]]
    end = index

    if "% ABV" not in lines[index].upper() and index + 1 < len(lines):
        next_line = lines[index + 1]
        if re.fullmatch(r"\d+(?:\.\d+)?% ABV", next_line.upper()):
            spec_lines.append(next_line)
            end = index + 1

    return " ".join(spec_lines), end


def find_name_start(lines: list[str], spec_index: int) -> int:
    start = spec_index - 1
    while start > 0 and is_upperish(lines[start - 1]) and not is_spec_line(lines[start - 1]):
        start -= 1
    return start


def parse_spec(spec: str) -> tuple[str | None, str | None, float | None]:
    abv_match = re.search(r"(\d+(?:\.\d+)?)% ABV", spec, flags=re.IGNORECASE)
    abv = float(abv_match.group(1)) if abv_match else None

    without_abv = re.sub(r"\d+(?:\.\d+)?% ABV", "", spec, flags=re.IGNORECASE).strip()
    if ":" in without_abv:
        style, region = without_abv.split(":", 1)
        return style.strip().title(), region.strip().title() or None, abv

    return without_abv.strip().title() or None, None, abv


def parse_age(name: str) -> int | None:
    match = re.search(r"(\d+)[-\s]?YEAR-OLD", name, flags=re.IGNORECASE)
    return int(match.group(1)) if match else None


def slugify(value: str) -> str:
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", "-", value).strip("-")
    return value or "unknown"


def join_wrapped_lines(lines: list[str]) -> str:
    text = " ".join(lines)
    text = re.sub(r"(\w)-\s+(\w)", r"\1\2", text)
    return re.sub(r"\s+", " ", text).strip()


def split_trailing_brand_note(lines: list[str]) -> tuple[list[str], list[str]]:
    for index, line in enumerate(lines):
        if re.match(r"^In \d{4},", line):
            return lines[:index], lines[index:]
    return lines, []


def first_present(records: list[dict[str, Any]], key: str) -> Any:
    return next((record[key] for record in records if record.get(key)), None)


def merge_descriptions(records: list[dict[str, Any]]) -> str:
    descriptions: list[str] = []
    seen: set[str] = set()
    for record in sorted(records, key=lambda item: item.get("source_page") or 0):
        description = record.get("brand_description")
        if description and description not in seen:
            descriptions.append(description)
            seen.add(description)
    return " ".join(descriptions)


def reassign_continuation_brands(records: list[dict[str, Any]]) -> None:
    records_by_page: dict[int, list[dict[str, Any]]] = {}
    for record in records:
        records_by_page.setdefault(record["source_page"], []).append(record)

    for page in sorted(records_by_page):
        page_records = records_by_page[page]
        previous_records = records_by_page.get(page - 1)
        if not previous_records:
            continue

        previous_brands = {
            record["brand_or_distillery"]
            for record in previous_records
            if record.get("brand_description") or record.get("country") or record.get("website")
        }
        if not previous_brands:
            continue

        for record in page_records:
            if record.get("country") or record.get("website"):
                continue

            current_brand = record["brand_or_distillery"]
            for previous_brand in previous_brands:
                if any(
                    previous_record["name"].startswith(f"{current_brand} ")
                    for previous_record in previous_records
                ):
                    record["brand_or_distillery"] = previous_brand
                    break


def enrich_records_by_brand(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    reassign_continuation_brands(records)

    by_brand: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        by_brand.setdefault(record["brand_or_distillery"], []).append(record)

    for brand_records in by_brand.values():
        combined_brand_description = merge_descriptions(brand_records)
        country = first_present(brand_records, "country")
        website = first_present(brand_records, "website")
        owner = first_present(brand_records, "owner")

        for record in brand_records:
            if combined_brand_description:
                record["brand_description"] = combined_brand_description
            record["country"] = record.get("country") or country
            record["website"] = record.get("website") or website
            record["owner"] = record.get("owner") or owner

    return records


def page_asset_paths(page_dir: Path, product_count: int, product_index: int) -> tuple[str | None, str | None, str]:
    page_image = page_dir / "page_render.png"
    embedded_images = sorted(page_dir.glob("embedded_image_*.*"))

    if not embedded_images:
        return str(page_image) if page_image.exists() else None, None, "none"

    if product_count == 1:
        confidence = "high"
    elif product_index == 0:
        confidence = "medium"
    else:
        confidence = "low"

    return (
        str(page_image) if page_image.exists() else None,
        str(embedded_images[0]),
        confidence,
    )


def parse_page(page_dir: Path) -> list[dict[str, Any]]:
    text_path = page_dir / "text.txt"
    lines = clean_lines(text_path.read_text(encoding="utf-8"))
    if not lines:
        return []

    page_match = re.search(r"page_(\d+)", page_dir.name)
    source_page = int(page_match.group(1)) if page_match else None
    first_product_name_start = None
    product_specs: list[tuple[int, int, int, str]] = []
    for index, line in enumerate(lines):
        if not is_spec_line(line):
            continue
        if (
            line.upper() in STYLE_PREFIXES
            and index + 1 < len(lines)
            and is_spec_line(lines[index + 1])
        ):
            continue
        name_start = find_name_start(lines, index)
        if name_start >= index:
            continue
        spec, spec_end = spec_span(lines, index)
        product_specs.append((name_start, index, spec_end, spec))
        if first_product_name_start is None or name_start < first_product_name_start:
            first_product_name_start = name_start

    if first_product_name_start is None:
        return []

    brand_parts = [lines[0]]
    brand_end = 1
    while brand_end < first_product_name_start:
        line = lines[brand_end]
        if line in COUNTRIES or line.startswith("Owner:") or line.startswith("www."):
            break
        if not is_upperish(line):
            break
        brand_parts.append(line)
        brand_end += 1

    brand = join_wrapped_lines(brand_parts)
    header_lines = lines[brand_end:first_product_name_start]
    country = next((line for line in header_lines[:4] if line in COUNTRIES), None)

    metadata_stop = 0
    for index, line in enumerate(header_lines):
        if line == country or line.startswith("www.") or line.startswith("Owner:"):
            metadata_stop = index + 1
            continue
        if metadata_stop > 0 and "," in line:
            metadata_stop = index + 1
            continue
        break

    metadata_lines = header_lines[:metadata_stop]
    website = next((line for line in metadata_lines if line.startswith("www.")), None)
    owner = next(
        (line.replace("Owner:", "").strip() for line in metadata_lines if line.startswith("Owner:")),
        None,
    )
    brand_description = join_wrapped_lines(header_lines[metadata_stop:])

    records: list[dict[str, Any]] = []
    trailing_brand_note = ""
    for product_index, (name_start, spec_start, spec_end, spec) in enumerate(product_specs):
        next_name_start = (
            product_specs[product_index + 1][0]
            if product_index + 1 < len(product_specs)
            else len(lines)
        )
        name = join_wrapped_lines(lines[name_start:spec_start])
        description_lines = lines[spec_end + 1 : next_name_start]
        if product_index == len(product_specs) - 1:
            description_lines, note_lines = split_trailing_brand_note(description_lines)
            trailing_brand_note = join_wrapped_lines(note_lines)
        description = join_wrapped_lines(description_lines)
        style, region, abv = parse_spec(spec)
        page_image_path, product_image_path, image_confidence = page_asset_paths(
            page_dir, len(product_specs), product_index
        )

        confidence = "high" if name and style and description else "medium"
        if not abv:
            confidence = "medium"

        records.append(
            {
                "product_id": f"p{source_page:04d}-{slugify(name)}" if source_page else slugify(name),
                "name": name,
                "brand_or_distillery": brand,
                "country": country,
                "region": region,
                "style": style,
                "age": parse_age(name),
                "abv": abv,
                "description": description,
                "brand_description": brand_description,
                "source_page": source_page,
                "page_image_path": page_image_path,
                "product_image_path": product_image_path,
                "image_confidence": image_confidence,
                "parse_confidence": confidence,
                "website": website,
                "owner": owner,
                "raw_block": "\n".join(lines[name_start:next_name_start]),
            }
        )

    if trailing_brand_note:
        brand_description = " ".join(part for part in (brand_description, trailing_brand_note) if part)
        for record in records:
            record["brand_description"] = brand_description

    return records


def parse_pages(input_dir: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for page_dir in sorted(input_dir.glob("page_*")):
        if page_dir.is_dir() and (page_dir / "text.txt").exists():
            records.extend(parse_page(page_dir))
    return enrich_records_by_brand(records)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prototype product parser for PyMuPDF page text.")
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=Path("data/extracted/pymupdf_probe"),
        help="Directory containing page_XXXX/text.txt outputs from the PyMuPDF probe.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("data/extracted/product_parse_sample.jsonl"),
        help="JSONL path for parsed product records.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    records = parse_pages(args.input_dir)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records),
        encoding="utf-8",
    )

    pages = sorted({record["source_page"] for record in records})
    print(f"records={len(records)} pages={len(pages)} out={args.out}")
    for record in records[:10]:
        print(
            f"page={record['source_page']} name={record['name']} "
            f"style={record['style']} region={record['region']} abv={record['abv']} "
            f"parse_confidence={record['parse_confidence']} "
            f"image_confidence={record['image_confidence']}"
        )


if __name__ == "__main__":
    main()
