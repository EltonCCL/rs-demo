from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class CatalogueValidationConfig:
    catalogue_path: Path = Path("data/extracted/product_parse_sample.jsonl")
    manifest_path: Path = Path("data/extracted/pymupdf_probe/manifest.json")
    output_path: Path = Path("data/extracted/catalogue_validation_report.md")


class CatalogueValidator:
    def build_report(self, records: list[dict[str, Any]], manifest: list[dict[str, Any]]) -> str:
        return build_report(records, manifest)

    def run(self, config: CatalogueValidationConfig) -> str:
        records = load_jsonl(config.catalogue_path)
        manifest = load_manifest(config.manifest_path)
        report = self.build_report(records, manifest)
        config.output_path.parent.mkdir(parents=True, exist_ok=True)
        config.output_path.write_text(report, encoding="utf-8")
        return report


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def load_manifest(path: Path) -> list[dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8"))


def compact_ranges(values: list[int]) -> list[str]:
    if not values:
        return []

    ranges: list[str] = []
    start = previous = values[0]
    for value in values[1:]:
        if value == previous + 1:
            previous = value
            continue
        ranges.append(str(start) if start == previous else f"{start}-{previous}")
        start = previous = value

    ranges.append(str(start) if start == previous else f"{start}-{previous}")
    return ranges


def markdown_table(headers: list[str], rows: list[list[Any]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(format_cell(value) for value in row) + " |")
    return "\n".join(lines)


def format_cell(value: Any) -> str:
    if value is None:
        return ""
    return str(value).replace("|", "\\|").replace("\n", " ")


def records_by_page(records: list[dict[str, Any]]) -> dict[int, list[dict[str, Any]]]:
    grouped: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        grouped[record["source_page"]].append(record)
    return grouped


def suspicious_name(record: dict[str, Any]) -> bool:
    name = record["name"]
    return "W H I S K" in name or len(name) > 80 or name != name.strip()


def build_report(records: list[dict[str, Any]], manifest: list[dict[str, Any]]) -> str:
    parsed_pages = sorted({record["source_page"] for record in records})
    all_pages = sorted(page["page"] for page in manifest)
    missing_pages = [page for page in all_pages if page not in parsed_pages]
    grouped_by_page = records_by_page(records)

    parse_confidence = Counter(record["parse_confidence"] for record in records)
    image_confidence = Counter(record["image_confidence"] for record in records)
    style_counts = Counter(record["style"] or "missing" for record in records)
    country_counts = Counter(record["country"] or "missing" for record in records)

    missing_abv = [record for record in records if record["abv"] is None]
    missing_country = [record for record in records if record["country"] is None]
    suspicious_names = [record for record in records if suspicious_name(record)]
    rare_styles = sorted((style, count) for style, count in style_counts.items() if count <= 2)
    multi_product_pages = sorted(
        (page, len(page_records))
        for page, page_records in grouped_by_page.items()
        if len(page_records) >= 3
    )

    sections = [
        "# Catalogue Validation Report",
        "",
        "## Summary",
        "",
        markdown_table(
            ["Metric", "Value"],
            [
                ["records", len(records)],
                ["pages in manifest", len(all_pages)],
                ["pages with parsed products", len(parsed_pages)],
                ["skipped page ranges", ", ".join(compact_ranges(missing_pages))],
                ["records missing ABV", len(missing_abv)],
                ["records missing country", len(missing_country)],
                ["suspicious names", len(suspicious_names)],
            ],
        ),
        "",
        "## Parse Confidence",
        "",
        markdown_table(["Confidence", "Count"], sorted(parse_confidence.items())),
        "",
        "## Image Confidence",
        "",
        markdown_table(["Confidence", "Count"], sorted(image_confidence.items())),
        "",
        "## Top Styles",
        "",
        markdown_table(["Style", "Count"], style_counts.most_common(25)),
        "",
        "## Top Countries",
        "",
        markdown_table(["Country", "Count"], country_counts.most_common(25)),
        "",
        "## Medium Confidence Records",
        "",
        markdown_table(
            ["Page", "Product", "Style", "ABV"],
            [
                [record["source_page"], record["name"], record["style"], record["abv"]]
                for record in records
                if record["parse_confidence"] == "medium"
            ],
        ),
        "",
        "## Missing ABV",
        "",
        markdown_table(
            ["Page", "Product", "Style"],
            [[record["source_page"], record["name"], record["style"]] for record in missing_abv],
        ),
        "",
        "## Suspicious Names",
        "",
        markdown_table(
            ["Page", "Product", "Style"],
            [
                [record["source_page"], record["name"], record["style"]]
                for record in suspicious_names
            ],
        ),
        "",
        "## Rare Styles",
        "",
        markdown_table(["Style", "Count"], rare_styles),
        "",
        "## Multi-Product Pages",
        "",
        markdown_table(["Page", "Record Count"], multi_product_pages),
        "",
        "## Skipped Pages",
        "",
        markdown_table(
            ["Page", "Text Chars", "Images", "Text Snippet"],
            [
                [
                    page["page"],
                    page["text_chars"],
                    page["embedded_image_count"],
                    page["text_snippet"][:140],
                ]
                for page in manifest
                if page["page"] in set(missing_pages)
            ],
        ),
        "",
    ]
    return "\n".join(sections)
