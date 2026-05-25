from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class MarkdownExportConfig:
    catalogue_path: Path = Path("data/extracted/product_parse_sample.jsonl")
    output_dir: Path = Path("data/extracted/product_markdown")


class ProductMarkdownExporter:
    def render_product(self, record: dict[str, Any], out_dir: Path) -> str:
        return product_markdown(record, out_dir)

    def write_products(self, records: list[dict[str, Any]], out_dir: Path) -> None:
        write_product_markdown(records, out_dir)

    def write_index(self, records: list[dict[str, Any]], out_dir: Path) -> None:
        write_index(records, out_dir)

    def run(self, config: MarkdownExportConfig) -> list[dict[str, Any]]:
        records = load_jsonl(config.catalogue_path)
        self.write_products(records, config.output_dir)
        self.write_index(records, config.output_dir)
        return records


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def format_value(value: Any) -> str:
    if value is None or value == "":
        return "Not extracted"
    return str(value)


def relative_link(from_dir: Path, target: str | None) -> str | None:
    if not target:
        return None
    target_path = Path(target)
    if not target_path.is_absolute():
        target_path = Path.cwd() / target_path
    return os.path.relpath(target_path, from_dir)


def markdown_table(rows: list[tuple[str, Any]]) -> str:
    lines = ["| Field | Value |", "|---|---|"]
    for key, value in rows:
        escaped_value = format_value(value).replace("|", r"\|")
        lines.append(f"| {key} | {escaped_value} |")
    return "\n".join(lines)


def product_markdown(record: dict[str, Any], out_dir: Path) -> str:
    cropped_product_image = relative_link(out_dir, record.get("cropped_product_image_path"))
    product_image = relative_link(out_dir, record.get("product_image_path"))
    page_image = relative_link(out_dir, record.get("page_image_path"))

    lines = [
        f"# {record['name']}",
        "",
        markdown_table(
            [
                ("Product ID", record["product_id"]),
                ("Brand / Distillery", record["brand_or_distillery"]),
                ("Country", record["country"]),
                ("Region", record["region"]),
                ("Style", record["style"]),
                ("Age", record["age"]),
                ("ABV", record["abv"]),
                ("Source Page", record["source_page"]),
                ("Parse Confidence", record["parse_confidence"]),
                ("Image Confidence", record["image_confidence"]),
                ("Website", record["website"]),
                ("Owner", record["owner"]),
            ]
        ),
        "",
        "## Product Description",
        "",
        format_value(record["description"]),
        "",
        "## Brand Description",
        "",
        format_value(record["brand_description"]),
        "",
        "## Images",
        "",
    ]

    if product_image:
        if cropped_product_image:
            lines.extend(
                [
                    "### Cropped Product Image",
                    "",
                    f"![Cropped product image]({cropped_product_image})",
                    "",
                    "### Original Embedded Image",
                    "",
                    f"![Original embedded image]({product_image})",
                    "",
                ]
            )
        else:
            lines.extend(["### Product / Embedded Image", "", f"![Product image]({product_image})", ""])
    else:
        lines.extend(["No product image extracted.", ""])

    if page_image:
        lines.extend(["### Full Page Render", "", f"![Page render]({page_image})", ""])
    else:
        lines.extend(["No page render extracted.", ""])

    lines.extend(["## Raw Parsed Block", "", "```text", record["raw_block"], "```", ""])
    return "\n".join(lines)


def write_product_markdown(records: list[dict[str, Any]], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    for record in sorted(records, key=lambda item: (item["source_page"], item["product_id"])):
        path = out_dir / f"{record['product_id']}.md"
        path.write_text(product_markdown(record, out_dir), encoding="utf-8")


def write_index(records: list[dict[str, Any]], out_dir: Path) -> None:
    lines = [
        "# Product Manual Review Index",
        "",
        f"Total products: {len(records)}",
        "",
        "| Page | Product | Style | Parse | Image |",
        "|---|---|---|---|---|",
    ]
    for record in sorted(records, key=lambda item: (item["source_page"], item["name"])):
        filename = f"{record['product_id']}.md"
        product = f"[{record['name']}]({filename})"
        row = [
            str(record["source_page"]),
            product,
            format_value(record["style"]),
            format_value(record["parse_confidence"]),
            format_value(record["image_confidence"]),
        ]
        lines.append("| " + " | ".join(value.replace("|", "\\|") for value in row) + " |")

    (out_dir / "index.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
