from __future__ import annotations

from pathlib import Path

import pytest

from rs_demo.cli import build_parser
from rs_demo.cli import main


def test_cli_exposes_pipeline_commands() -> None:
    parser = build_parser()

    args = parser.parse_args(["parse-products", "--out", "out.jsonl"])
    assert args.command == "parse-products"
    assert str(args.out) == "out.jsonl"

    args = parser.parse_args(["build-mock-embeddings", "--dimension", "8"])
    assert args.command == "build-mock-embeddings"
    assert args.dimension == 8

    args = parser.parse_args(["build-mock-query-embeddings", "--dimension", "8"])
    assert args.command == "build-mock-query-embeddings"
    assert args.dimension == 8

    args = parser.parse_args(["run-mock-evaluation", "--top-k", "5"])
    assert args.command == "run-mock-evaluation"
    assert args.top_k == 5

    args = parser.parse_args(["build-gemini-embeddings", "--mode", "text", "--limit-products", "10"])
    assert args.command == "build-gemini-embeddings"
    assert args.mode == "text"
    assert args.limit_products == 10

    args = parser.parse_args(["build-gemini-query-embeddings", "--mode", "text"])
    assert args.command == "build-gemini-query-embeddings"
    assert args.mode == "text"

    args = parser.parse_args(["run-gemini-evaluation", "--mode", "text"])
    assert args.command == "run-gemini-evaluation"
    assert args.mode == "text"


def test_build_mock_query_embeddings_fails_on_missing_modalities(tmp_path: Path) -> None:
    text_queries = tmp_path / "text_queries.jsonl"
    text_queries.write_text(
        (
            '{"query_id": "q001", "query_type": "text", "query_style": "metadata_brand", '
            '"query": "I want A.", "relevant_product_ids": ["p001"]}\n'
        ),
        encoding="utf-8",
    )

    with pytest.raises(FileNotFoundError, match="missing image query file"):
        main(
            [
                "build-mock-query-embeddings",
                "--text-queries",
                str(text_queries),
                "--image-queries",
                str(tmp_path / "missing_image_queries.jsonl"),
                "--image-text-queries",
                str(tmp_path / "missing_image_text_queries.jsonl"),
                "--output-dir",
                str(tmp_path / "queries"),
            ]
        )
