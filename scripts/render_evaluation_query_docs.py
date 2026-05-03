#!/usr/bin/env python3
"""Regenerate docs/evaluation_queries_and_labels.md and sync query images into docs/eval_query_images/.

Copies movie-scene query images into docs/ so GitHub can render them from the markdown file.
Run from repo root: python scripts/render_evaluation_query_docs.py
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


def label_generation_block(record: dict) -> list[str] | None:
    lg = record.get("label_generation")
    if not lg:
        return None
    method = lg.get("method", "")
    rule = lg.get("rule") or lg.get("source_fields")
    lines = [
        "<details>",
        "<summary>Label rule (how positives were chosen)</summary>",
        "",
        f"*Method:* `{method}`",
        "",
        f"*Rule / fields:* {rule}",
        "",
        "</details>",
        "",
    ]
    return lines


def relevant_products_section(pids: list[str], products: dict[str, str]) -> list[str]:
    """Readable names by default; IDs only inside a collapsed block."""
    lines: list[str] = []
    lines.append("**Expected positives (catalogue products):**")
    lines.append("")
    for pid in pids:
        nm = products.get(pid)
        if nm:
            lines.append(f"- **{nm}**")
        else:
            lines.append(f"- **(unknown name)** — not found in local `product_parse_sample.jsonl`")
    lines.append("")
    lines.append("<details>")
    lines.append("<summary>Product IDs (<code>relevant_product_ids</code> in JSONL)</summary>")
    lines.append("")
    for pid in pids:
        lines.append(f"- `{pid}`")
    lines.append("")
    lines.append("</details>")
    lines.append("")
    return lines


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

    image_rel_paths: set[str] = set()
    for r in img_q:
        p = r.get("query_image_path")
        if p:
            image_rel_paths.add(str(p))
    for r in it_q:
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
        "Human-readable view of the evaluation queries in `data/eval/`: what each query asks, which "
        "catalogue products count as a hit, and (for visual queries) the stills used. Positives are **controlled "
        "seeds** (rules or manual scene mapping), not full human relevance judgments. Technical IDs and file "
        "paths are tucked under “details” blocks so this page stays easy to scan."
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
    lines.append("")
    lines.append("## Source files")
    lines.append("")
    lines.append("| File | Query type | Count |")
    lines.append("|------|------------|-------|")
    lines.append(f"| `data/eval/text_queries.jsonl` | text | {len(text_q)} |")
    lines.append(f"| `data/eval/image_queries.jsonl` | image (crop + scene pairs) | {len(img_q)} |")
    lines.append(f"| `data/eval/image_text_queries.jsonl` | image + text | {len(it_q)} |")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append('<a id="text-queries"></a>')
    lines.append("## Text queries")
    lines.append("")
    for r in text_q:
        qid = r["query_id"]
        lines.append(f"### {qid} — `{r.get('query_style', '')}`")
        lines.append("")
        lines.append(f"**Query:** {r.get('query', '')}")
        lines.append("")
        if r.get("notes"):
            lines.append(f"*Notes:* {r['notes']}")
            lines.append("")
        lg_block = label_generation_block(r)
        if lg_block:
            lines.extend(lg_block)
        lines.extend(relevant_products_section(r.get("relevant_product_ids") or [], products))

    lines.append("---")
    lines.append("")
    lines.append('<a id="image-queries"></a>')
    lines.append("## Image queries (cropped bottle and whole scene)")
    lines.append("")
    lines.append(
        "Each screen reference appears twice: `*_crop` (bottle crop) and `*_scene` (full still). "
        "**Expected relevant products** are the same for the pair."
    )
    lines.append("")
    pairs: OrderedDict[str, list[dict]] = OrderedDict()
    for r in img_q:
        sid = r.get("source_image_id") or r["query_id"].rsplit("_", 1)[0]
        pairs.setdefault(sid, []).append(r)

    for _sid, group in pairs.items():
        group = sorted(group, key=lambda x: x["query_id"])
        first = group[0]
        crop_row = next((x for x in group if str(x["query_id"]).endswith("_crop")), group[0])
        scene_row = next((x for x in group if str(x["query_id"]).endswith("_scene")), group[-1])
        crop_path = str(crop_row.get("query_image_path") or "")
        scene_path = str(scene_row.get("query_image_path") or "")

        lines.append(f"### {first.get('source_image_id', '')} — {first.get('screen_reference', '')}")
        lines.append("")
        lines.append(f"**Whisky reference (annotation):** {first.get('whisky_reference', '')}")
        lines.append("")
        lines.append("| Cropped bottle | Whole scene |")
        lines.append("|:--:|:--:|")
        cu = url_by_rel.get(crop_path)
        su = url_by_rel.get(scene_path)
        lines.append(
            f"| {img_tag(cu, 'Cropped bottle', 200)} | {img_tag(su, 'Whole scene', 360)} |"
        )
        lines.append("")
        ids = [r["query_id"] for r in group]
        lines.append(
            f"*Retrieval query IDs:* {', '.join(f'`{q}`' for q in ids)} "
            f"({crop_row.get('query_style', '')} / {scene_row.get('query_style', '')})."
        )
        lines.append("")
        lines.append("<details>")
        lines.append("<summary>Source image paths (under <code>data/eval/</code>)</summary>")
        lines.append("")
        for r in group:
            lines.append(f"- `{r.get('query_image_path', '')}`")
        lines.append("")
        lines.append("</details>")
        lines.append("")
        rel = first.get("relevant_product_ids") or []
        lines.extend(relevant_products_section(rel, products))

    lines.append("---")
    lines.append("")
    lines.append('<a id="image-text-queries"></a>')
    lines.append("## Image + text queries (whole scene + question)")
    lines.append("")
    lines.append(
        "Fixed question text: **What is the whisky in this image?** "
        "Each row uses the whole-scene image (same stills as the `*_scene` image-only queries where applicable)."
    )
    lines.append("")
    for r in it_q:
        qid = r["query_id"]
        lines.append(f"### {qid}")
        lines.append("")
        lines.append(f"**Screen:** {r.get('screen_reference', '')}  ")
        lines.append(f"**Whisky reference (annotation):** {r.get('whisky_reference', '')}")
        lines.append("")
        ip = str(r.get("query_image_path") or "")
        iu = url_by_rel.get(ip)
        lines.append(img_tag(iu, f"{qid} scene", 420))
        lines.append("")
        if r.get("notes"):
            lines.append(f"*Notes:* {r['notes']}")
            lines.append("")
        lines.append("<details>")
        lines.append("<summary>Source image path</summary>")
        lines.append("")
        lines.append(f"`{ip}`")
        lines.append("")
        lines.append("</details>")
        lines.append("")
        lines.extend(relevant_products_section(r.get("relevant_product_ids") or [], products))

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
