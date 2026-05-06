#!/usr/bin/env python3
"""Regenerate docs/evaluation_queries_and_labels.md and sync query images into docs/eval_query_images/.

Copies movie-scene query images into docs/ so GitHub can render them from the markdown file.
Run from repo root: python scripts/render_evaluation_query_docs.py

Change (2026-05): text / image / image+text sections each use one main HTML table; paths, rules, notes,
and JSONL IDs live in appendix <details> blocks.
"""
from __future__ import annotations

import json
import shutil
from collections import OrderedDict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
OUT_MD = DOCS / "evaluation_queries_and_labels.md"
IMG_OUT = DOCS / "eval_query_images"


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def esc_html(s: object) -> str:
    t = "" if s is None else str(s)
    return (
        t.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _label_rule_text(record: dict) -> str:
    lg = record.get("label_generation")
    if not lg:
        return ""
    method = lg.get("method", "")
    rule = lg.get("rule") or lg.get("source_fields")
    return f"{method} — {rule}"


def positives_ul(pids: list[str], products: dict[str, str]) -> str:
    parts = ["<ul>"]
    for pid in pids:
        nm = products.get(pid)
        if nm:
            parts.append(f"<li><strong>{esc_html(nm)}</strong></li>")
        else:
            parts.append("<li><em>(unknown in local catalogue)</em></li>")
    parts.append("</ul>")
    return "".join(parts)


def text_queries_main_table(text_q: list[dict], products: dict[str, str]) -> list[str]:
    """Single scan-friendly HTML table for all text evaluation queries."""
    out: list[str] = []
    out.append(
        "One row per benchmark query. **Expected positives** lists catalogue names that count as a hit "
        "(Hit@k / MRR). Notes and technical IDs are in the appendix below."
    )
    out.append("")
    out.append('<table>')
    out.append("<thead><tr>")
    out.append("<th align='left'>ID</th>")
    out.append("<th align='left'>Style</th>")
    out.append("<th align='left'>Query</th>")
    out.append("<th align='left'>Expected positives</th>")
    out.append("</tr></thead>")
    out.append("<tbody>")
    for r in text_q:
        qid = esc_html(r["query_id"])
        style = esc_html(r.get("query_style", ""))
        query = esc_html(r.get("query", ""))
        pids = r.get("relevant_product_ids") or []
        pos = positives_ul(pids, products)
        out.append("<tr>")
        out.append(f"<td valign='top'><code>{qid}</code></td>")
        out.append(f"<td valign='top'><code>{style}</code></td>")
        out.append(f"<td valign='top'>{query}</td>")
        out.append(f"<td valign='top'>{pos}</td>")
        out.append("</tr>")
    out.append("</tbody></table>")
    out.append("")
    return out


def text_queries_appendix_details(text_q: list[dict], products: dict[str, str]) -> list[str]:
    """Collapsed table: notes, how labelled, product IDs."""
    out: list[str] = []
    out.append("<details>")
    out.append("<summary><strong>Appendix (text queries):</strong> notes, label rules, product IDs</summary>")
    out.append("")
    out.append('<table>')
    out.append("<thead><tr>")
    out.append("<th align='left'>ID</th>")
    out.append("<th align='left'>Notes</th>")
    out.append("<th align='left'>How labelled</th>")
    out.append("<th align='left'>Product IDs</th>")
    out.append("</tr></thead><tbody>")
    for r in text_q:
        qid = esc_html(r["query_id"])
        notes = esc_html(r.get("notes") or "—")
        rule = esc_html(_label_rule_text(r) or "—")
        pids = r.get("relevant_product_ids") or []
        ids_cell = ", ".join(f"<code>{esc_html(pid)}</code>" for pid in pids)
        out.append("<tr>")
        out.append(f"<td valign='top'><code>{qid}</code></td>")
        out.append(f"<td valign='top'>{notes}</td>")
        out.append(f"<td valign='top'>{rule}</td>")
        out.append(f"<td valign='top'>{ids_cell}</td>")
        out.append("</tr>")
    out.append("</tbody></table>")
    out.append("")
    out.append("</details>")
    out.append("")
    return out


def image_query_pairs(img_q: list[dict]) -> OrderedDict[str, list[dict]]:
    pairs: OrderedDict[str, list[dict]] = OrderedDict()
    for r in img_q:
        sid = r.get("source_image_id") or r["query_id"].rsplit("_", 1)[0]
        pairs.setdefault(sid, []).append(r)
    return pairs


def image_queries_main_table(
    pairs: OrderedDict[str, list[dict]],
    url_by_rel: dict[str, str | None],
    products: dict[str, str],
) -> list[str]:
    out: list[str] = []
    out.append(
        "One row per movie/TV still. **Crop** vs **scene** are two image-only evaluation queries on the same "
        "frame; expected positives match. File paths and JSONL product IDs are in the appendix."
    )
    out.append("")
    out.append("<table>")
    out.append("<thead><tr>")
    for h in ("Still", "Screen", "Whisky (annotation)", "Query IDs", "Crop", "Scene", "Expected positives"):
        out.append(f"<th align='left'>{h}</th>")
    out.append("</tr></thead><tbody>")
    for _sid, group in pairs.items():
        group = sorted(group, key=lambda x: x["query_id"])
        first = group[0]
        crop_row = next((x for x in group if str(x["query_id"]).endswith("_crop")), group[0])
        scene_row = next((x for x in group if str(x["query_id"]).endswith("_scene")), group[-1])
        crop_path = str(crop_row.get("query_image_path") or "")
        scene_path = str(scene_row.get("query_image_path") or "")
        cu = url_by_rel.get(crop_path)
        su = url_by_rel.get(scene_path)
        still = esc_html(first.get("source_image_id", ""))
        screen = esc_html(first.get("screen_reference", ""))
        wref = esc_html(first.get("whisky_reference", ""))
        ids = ", ".join(f"<code>{esc_html(x['query_id'])}</code>" for x in group)
        rel = first.get("relevant_product_ids") or []
        pos = positives_ul(rel, products)
        out.append("<tr>")
        out.append(f"<td valign='top'><code>{still}</code></td>")
        out.append(f"<td valign='top'>{screen}</td>")
        out.append(f"<td valign='top'>{wref}</td>")
        out.append(f"<td valign='top'>{ids}</td>")
        out.append(f"<td valign='top'>{img_tag(cu, 'Bottle crop', 130)}</td>")
        out.append(f"<td valign='top'>{img_tag(su, 'Whole scene', 240)}</td>")
        out.append(f"<td valign='top'>{pos}</td>")
        out.append("</tr>")
    out.append("</tbody></table>")
    out.append("")
    return out


def image_queries_appendix_details(pairs: OrderedDict[str, list[dict]]) -> list[str]:
    out: list[str] = []
    out.append("<details>")
    out.append("<summary><strong>Appendix (image queries):</strong> paths and product IDs</summary>")
    out.append("")
    out.append("<table>")
    out.append("<thead><tr>")
    for h in ("Still", "Crop path", "Scene path", "Product IDs"):
        out.append(f"<th align='left'>{h}</th>")
    out.append("</tr></thead><tbody>")
    for _sid, group in pairs.items():
        group = sorted(group, key=lambda x: x["query_id"])
        first = group[0]
        crop_row = next((x for x in group if str(x["query_id"]).endswith("_crop")), group[0])
        scene_row = next((x for x in group if str(x["query_id"]).endswith("_scene")), group[-1])
        crop_path = str(crop_row.get("query_image_path") or "")
        scene_path = str(scene_row.get("query_image_path") or "")
        still = esc_html(first.get("source_image_id", ""))
        pids = ", ".join(
            f"<code>{esc_html(p)}</code>" for p in (first.get("relevant_product_ids") or [])
        )
        out.append("<tr>")
        out.append(f"<td valign='top'><code>{still}</code></td>")
        out.append(f"<td valign='top'><code>{esc_html(crop_path)}</code></td>")
        out.append(f"<td valign='top'><code>{esc_html(scene_path)}</code></td>")
        out.append(f"<td valign='top'>{pids}</td>")
        out.append("</tr>")
    out.append("</tbody></table>")
    out.append("")
    out.append("</details>")
    out.append("")
    return out


def image_text_main_table(
    it_q: list[dict],
    url_by_rel: dict[str, str | None],
    products: dict[str, str],
    image_column: str,
    image_width: int,
) -> list[str]:
    out: list[str] = []
    out.append("<table>")
    out.append("<thead><tr>")
    for h in ("ID", "Screen", "Whisky (annotation)", image_column, "Expected positives"):
        out.append(f"<th align='left'>{h}</th>")
    out.append("</tr></thead><tbody>")
    for r in it_q:
        qid = esc_html(r["query_id"])
        screen = esc_html(r.get("screen_reference", ""))
        wref = esc_html(r.get("whisky_reference", ""))
        ip = str(r.get("query_image_path") or "")
        iu = url_by_rel.get(ip)
        rel = r.get("relevant_product_ids") or []
        pos = positives_ul(rel, products)
        out.append("<tr>")
        out.append(f"<td valign='top'><code>{qid}</code></td>")
        out.append(f"<td valign='top'>{screen}</td>")
        out.append(f"<td valign='top'>{wref}</td>")
        rq = r["query_id"]
        out.append(f"<td valign='top'>{img_tag(iu, f'{rq} image', image_width)}</td>")
        out.append(f"<td valign='top'>{pos}</td>")
        out.append("</tr>")
    out.append("</tbody></table>")
    out.append("")
    return out


def image_text_appendix_details(it_q: list[dict], label: str) -> list[str]:
    out: list[str] = []
    out.append("<details>")
    out.append(f"<summary><strong>Appendix ({label}):</strong> paths, notes, product IDs</summary>")
    out.append("")
    out.append("<table>")
    out.append("<thead><tr>")
    for h in ("ID", "Source image path", "Notes", "Product IDs"):
        out.append(f"<th align='left'>{h}</th>")
    out.append("</tr></thead><tbody>")
    for r in it_q:
        qid = esc_html(r["query_id"])
        path = esc_html(str(r.get("query_image_path") or ""))
        notes = esc_html(r.get("notes") or "—")
        pids = ", ".join(
            f"<code>{esc_html(p)}</code>" for p in (r.get("relevant_product_ids") or [])
        )
        out.append("<tr>")
        out.append(f"<td valign='top'><code>{qid}</code></td>")
        out.append(f"<td valign='top'><code>{path}</code></td>")
        out.append(f"<td valign='top'>{notes}</td>")
        out.append(f"<td valign='top'>{pids}</td>")
        out.append("</tr>")
    out.append("</tbody></table>")
    out.append("")
    out.append("</details>")
    out.append("")
    return out


def copy_image_for_docs(rel_path: str, log: list[str]) -> str | None:
    """Copy repo-relative image into docs/eval_query_images/. Return relative URL for markdown."""
    src = ROOT / rel_path
    if not src.is_file():
        log.append(f"MISSING: {rel_path}")
        return None
    IMG_OUT.mkdir(parents=True, exist_ok=True)
    dest = IMG_OUT / src.name
    shutil.copy2(src, dest)
    return f"eval_query_images/{dest.name}"


def img_tag(url: str | None, alt: str, width: int) -> str:
    if not url:
        return f"<p><em>Image missing ({alt}).</em></p>"
    return f'<img src="{url}" alt="{_escape_attr(alt)}" width="{width}" />'


def _escape_attr(s: str) -> str:
    return s.replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;")


# One notebook per retrieval setting; paths are repo-relative (links from docs/ use ../notebooks/).
GEMINI_REVIEW_NOTEBOOKS: list[tuple[str, str, str]] = [
    ("1", "Text query → product text", "gemini_review_01_text_to_product_text.ipynb"),
    ("2", "Text query → product multimodal", "gemini_review_02_text_to_product_multimodal.ipynb"),
    ("3", "Cropped image → product image", "gemini_review_03_cropped_image_to_product_image.ipynb"),
    ("4", "Whole scene image → product image", "gemini_review_04_whole_image_to_product_image.ipynb"),
    ("5", "Cropped image → product multimodal", "gemini_review_05_cropped_image_to_product_multimodal.ipynb"),
    ("6", "Whole scene image → product multimodal", "gemini_review_06_whole_image_to_product_multimodal.ipynb"),
    ("7", "Whole image + text → product multimodal", "gemini_review_07_image_text_to_product_multimodal.ipynb"),
    (
        "8",
        "Cropped image + text → product image",
        "gemini_review_08_cropped_image_text_to_product_image.ipynb",
    ),
    (
        "9",
        "Cropped image + text → product multimodal",
        "gemini_review_09_cropped_image_text_to_product_multimodal.ipynb",
    ),
]


def gemini_review_notebooks_section() -> list[str]:
    lines: list[str] = []
    lines.append('<a id="gemini-ranking-notebooks"></a>')
    lines.append("## Inspect Gemini retrieval output (notebooks)")
    lines.append("")
    lines.append(
        "After you have run Gemini evaluation, open a notebook under `notebooks/` to browse **real rankings** "
        "per setting. Each loads `data/eval/gemini_retrieval_report.json`, the matching query/product embeddings, "
        "and catalogue rows **offline** (no API calls)."
    )
    lines.append("")
    lines.append("| # | Retrieval setting | Notebook |")
    lines.append("|---|------------------|----------|")
    for num, title, filename in GEMINI_REVIEW_NOTEBOOKS:
        lines.append(
            f"| {num} | {title} | [`{filename}`](../notebooks/{filename}) |"
        )
    lines.append("")
    return lines


def render() -> str:
    log: list[str] = []
    products: dict[str, str] = {}
    product_path = ROOT / "data/extracted/product_parse_sample.jsonl"
    if product_path.is_file():
        for r in load_jsonl(product_path):
            products[r["product_id"]] = (r.get("name") or r["product_id"]).strip()

    text_q = load_jsonl(ROOT / "data/eval/text_queries.jsonl")
    img_q = load_jsonl(ROOT / "data/eval/image_queries.jsonl")
    it_q = load_jsonl(ROOT / "data/eval/image_text_queries.jsonl")
    crop_it_q = load_jsonl(ROOT / "data/eval/cropped_image_text_queries.jsonl")

    image_rel_paths: set[str] = set()
    for r in img_q:
        p = r.get("query_image_path")
        if p:
            image_rel_paths.add(str(p))
    for r in it_q:
        p = r.get("query_image_path")
        if p:
            image_rel_paths.add(str(p))
    for r in crop_it_q:
        p = r.get("query_image_path")
        if p:
            image_rel_paths.add(str(p))

    url_by_rel: dict[str, str | None] = {}
    for rel in sorted(image_rel_paths):
        url_by_rel[rel] = copy_image_for_docs(rel, log)

    lines: list[str] = []
    lines.append("# Evaluation queries and expected labels")
    lines.append("")
    lines.append(
        "Human-readable view of the evaluation queries in `data/eval/`. **Text**, **image** (crop/scene pairs), "
        "**whole image + text**, and **cropped image + text** benchmarks are each a single HTML table "
        "(queries, thumbnails where relevant, expected catalogue names). Positives are **controlled seeds** "
        "(rules or manual scene mapping), not full human relevance judgments. Paths, notes, rules, and JSONL "
        "product IDs sit in collapsed **appendix** blocks."
    )
    lines.append("")
    lines.append(
        "Scene and crop pictures are copied into [`docs/eval_query_images/`](eval_query_images/) so they display "
        "on GitHub."
    )
    lines.append("")
    lines.append("## Table of contents")
    lines.append("")
    lines.append("- [Text queries](#text-queries)")
    lines.append("- [Image queries](#image-queries)")
    lines.append("- [Image + text queries](#image-text-queries)")
    lines.append("- [Cropped image + text queries](#cropped-image-text-queries)")
    lines.append("- [Gemini ranking notebooks](#gemini-ranking-notebooks)")
    lines.append("")
    lines.append("## Source files")
    lines.append("")
    lines.append("| File | Query type | Count |")
    lines.append("|------|------------|-------|")
    lines.append(f"| `data/eval/text_queries.jsonl` | text | {len(text_q)} |")
    lines.append(f"| `data/eval/image_queries.jsonl` | image (crop + scene pairs) | {len(img_q)} |")
    lines.append(f"| `data/eval/image_text_queries.jsonl` | whole image + text | {len(it_q)} |")
    lines.append(
        f"| `data/eval/cropped_image_text_queries.jsonl` | cropped image + text | {len(crop_it_q)} |"
    )
    lines.append("")
    lines.extend(gemini_review_notebooks_section())
    lines.append("---")
    lines.append("")
    lines.append('<a id="text-queries"></a>')
    lines.append("## Text queries")
    lines.append("")
    lines.extend(text_queries_main_table(text_q, products))
    lines.extend(text_queries_appendix_details(text_q, products))

    lines.append("---")
    lines.append("")
    lines.append('<a id="image-queries"></a>')
    lines.append("## Image queries (cropped bottle and whole scene)")
    lines.append("")
    pairs = image_query_pairs(img_q)
    lines.extend(image_queries_main_table(pairs, url_by_rel, products))
    lines.extend(image_queries_appendix_details(pairs))

    lines.append("---")
    lines.append("")
    lines.append('<a id="image-text-queries"></a>')
    lines.append("## Image + text queries (whole scene + question)")
    lines.append("")
    lines.append(
        "Fixed question for every row: **What is the whisky in this image?** "
        "Scenes align with the image-only `*_scene` queries where the source still is shared."
    )
    lines.append("")
    lines.extend(image_text_main_table(it_q, url_by_rel, products, "Scene", 260))
    lines.extend(image_text_appendix_details(it_q, "whole image + text"))

    lines.append("---")
    lines.append("")
    lines.append('<a id="cropped-image-text-queries"></a>')
    lines.append("## Cropped image + text queries (bottle crop + same question)")
    lines.append("")
    lines.append(
        "Fixed question for every row: **What is the whisky in this image?** "
        "These queries use the same bottle crops as the image-only `*_crop` queries. "
        "The text is intentionally identical to the whole-scene image-text set so the experiment can isolate "
        "the effect of query-image cleanliness."
    )
    lines.append("")
    lines.extend(image_text_main_table(crop_it_q, url_by_rel, products, "Crop", 140))
    lines.extend(image_text_appendix_details(crop_it_q, "cropped image + text"))

    lines.append("---")
    lines.append("")
    lines.append("## Regenerating this page")
    lines.append("")
    lines.append("From the repository root:")
    lines.append("")
    lines.append("```bash")
    lines.append("python scripts/render_evaluation_query_docs.py")
    lines.append("```")
    lines.append("")
    if log:
        lines.append("<!-- Generator warnings:")
        for w in log:
            lines.append(f"  - {w}")
        lines.append("-->")
        lines.append("")

    return "\n".join(lines) + "\n"


def main() -> None:
    OUT_MD.write_text(render(), encoding="utf-8")
    print(f"Wrote {OUT_MD.relative_to(ROOT)}")
    n = len(list(IMG_OUT.glob("*"))) if IMG_OUT.is_dir() else 0
    print(f"Images in {IMG_OUT.relative_to(ROOT)}: {n}")


if __name__ == "__main__":
    main()
