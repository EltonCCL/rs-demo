from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path
from typing import Any

from rs_demo.rag import GeminiFileSearchClient, RagQueryResult, load_store_name


DEFAULT_QUERIES = [
    {
        "query_id": "visual_round_bottle",
        "query": "I want to buy a whisky with round bottle",
    },
    {
        "query_id": "visual_green_bottle",
        "query": "I want to buy a whisky in green bottle.",
    },
    {
        "query_id": "visual_ball_shaped_bottle",
        "query": "I want to buy a whisky in ball-shaped bottle",
    },
]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the two qualitative visual-attribute text queries against a RAG store."
    )
    parser.add_argument("--store-manifest", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--catalogue", type=Path, default=Path("data/extracted/product_parse_sample.jsonl"))
    parser.add_argument("--target-store", default="rag_product_image_store")
    parser.add_argument("--model", default="gemini-3.1-flash-lite")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--sleep-seconds", type=float, default=5.0)
    parser.add_argument("--max-retries", type=int, default=5)
    parser.add_argument("--retry-sleep-seconds", type=float, default=20.0)
    parser.add_argument(
        "--refresh-summary-only",
        action="store_true",
        help="Regenerate the Markdown summary from --out without calling the API.",
    )
    parser.add_argument(
        "--no-resume",
        action="store_true",
        help="Ignore existing --out results and rerun every probe query.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    product_image_paths = load_product_image_paths(args.catalogue)
    if args.refresh_summary_only:
        payload = json.loads(args.out.read_text(encoding="utf-8"))
        args.summary.parent.mkdir(parents=True, exist_ok=True)
        args.summary.write_text(
            render_summary(payload, product_image_paths, args.summary),
            encoding="utf-8",
        )
        print(f"Wrote {args.summary}")
        return

    store_name = load_store_name(args.store_manifest)
    client = GeminiFileSearchClient()

    raw_by_query_id = load_existing_results(args.out) if not args.no_resume else {}
    for index, query in enumerate(DEFAULT_QUERIES, start=1):
        if query["query_id"] in raw_by_query_id:
            continue
        result = run_query_with_retries(
            client=client,
            store_name=store_name,
            query_id=query["query_id"],
            query=query["query"],
            top_k=args.top_k,
            model_name=args.model,
            max_retries=args.max_retries,
            retry_sleep_seconds=args.retry_sleep_seconds,
        )
        raw_by_query_id[query["query_id"]] = result
        write_outputs(args, store_name, ordered_results(raw_by_query_id), product_image_paths)
        if index < len(DEFAULT_QUERIES) and args.sleep_seconds > 0:
            time.sleep(args.sleep_seconds)

    raw_results = ordered_results(raw_by_query_id)
    write_outputs(args, store_name, raw_results, product_image_paths)
    print(f"Wrote {args.out} and {args.summary}")
    for result in raw_results:
        product_ids = [product["product_id"] for product in result.get("ranked_products", [])]
        print(f"{result['query_id']}: {product_ids}")


def run_query_with_retries(
    client: GeminiFileSearchClient,
    store_name: str,
    query_id: str,
    query: str,
    top_k: int,
    model_name: str,
    max_retries: int,
    retry_sleep_seconds: float,
) -> dict[str, Any]:
    last_error: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            result = client.search_products(
                store_name=store_name,
                query_id=query_id,
                query=query,
                query_type="text",
                image_path=None,
                top_k=top_k,
                model_name=model_name,
            )
            return result.to_dict()
        except Exception as exc:
            last_error = exc
            if attempt >= max_retries:
                break
            time.sleep(retry_sleep_seconds)

    assert last_error is not None
    return RagQueryResult(
        query_id=query_id,
        query=query,
        raw_text=json.dumps(
            {
                "error": {
                    "type": type(last_error).__name__,
                    "message": str(last_error),
                }
            }
        ),
        ranked_products=[],
    ).to_dict()


def load_existing_results(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {
        str(result["query_id"]): result
        for result in payload.get("raw_results", [])
        if result.get("query_id")
        and result.get("ranked_products")
        and not result_contains_error(result)
    }


def result_contains_error(result: dict[str, Any]) -> bool:
    try:
        payload = json.loads(str(result.get("raw_text") or "{}"))
    except json.JSONDecodeError:
        return False
    return isinstance(payload, dict) and "error" in payload


def ordered_results(raw_by_query_id: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        raw_by_query_id[query["query_id"]]
        for query in DEFAULT_QUERIES
        if query["query_id"] in raw_by_query_id
    ]


def write_outputs(
    args: argparse.Namespace,
    store_name: str,
    raw_results: list[dict[str, Any]],
    product_image_paths: dict[str, str],
) -> None:
    payload = {
        "model": args.model,
        "query_type": "text",
        "queries": DEFAULT_QUERIES,
        "raw_results": raw_results,
        "store_manifest": args.store_manifest.as_posix(),
        "store_name": store_name,
        "target_store": args.target_store,
        "top_k": args.top_k,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.summary.parent.mkdir(parents=True, exist_ok=True)
    args.summary.write_text(
        render_summary(payload, product_image_paths, args.summary),
        encoding="utf-8",
    )


def render_summary(
    payload: dict[str, Any],
    product_image_paths: dict[str, str],
    summary_path: Path,
) -> str:
    lines = [
        "# Gemini RAG Visual Text Probe",
        "",
        f"Store: `{payload['store_name']}`",
        f"Target store: `{payload['target_store']}`",
        "",
        "| Query | Rank | Image | Product ID | Product name | Reason |",
        "|---|---:|---|---|---|---|",
    ]
    for result in payload["raw_results"]:
        products = result.get("ranked_products") or []
        if not products:
            lines.append(f"| {escape_cell(result['query'])} | - | - | - | - | no result |")
            continue
        for product in products:
            product_id = str(product.get("product_id") or "")
            lines.append(
                "| "
                f"{escape_cell(result['query'])} | "
                f"{product.get('rank')} | "
                f"{image_cell(product_id, product_image_paths, summary_path)} | "
                f"`{escape_cell(product_id)}` | "
                f"{escape_cell(product.get('product_name'))} | "
                f"{escape_cell(product.get('reason'))} |"
            )
    return "\n".join(lines) + "\n"


def load_product_image_paths(catalogue_path: Path) -> dict[str, str]:
    image_paths: dict[str, str] = {}
    for line in catalogue_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        image_path = record.get("cropped_product_image_path") or record.get("product_image_path")
        if image_path:
            image_paths[str(record["product_id"])] = str(image_path)
    return image_paths


def image_cell(product_id: str, product_image_paths: dict[str, str], summary_path: Path) -> str:
    image_path = product_image_paths.get(product_id)
    if not image_path:
        return ""
    path = Path(image_path)
    if path.is_absolute():
        src = path.as_posix()
    else:
        src = Path(os.path.relpath(path, start=summary_path.parent)).as_posix()
    return f'<img src="{escape_html_attr(src)}" width="70">'


def escape_cell(value: object) -> str:
    return str(value or "").replace("|", "\\|").replace("\n", " ")


def escape_html_attr(value: object) -> str:
    return (
        str(value or "")
        .replace("&", "&amp;")
        .replace('"', "&quot;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


if __name__ == "__main__":
    main()
