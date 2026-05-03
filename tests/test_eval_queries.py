from __future__ import annotations

import json
from pathlib import Path

CATALOGUE_PATH = Path("data/extracted/product_parse_sample.jsonl")
TEXT_QUERIES_PATH = Path("data/eval/text_queries.jsonl")
IMAGE_QUERIES_PATH = Path("data/eval/image_queries.jsonl")
IMAGE_TEXT_QUERIES_PATH = Path("data/eval/image_text_queries.jsonl")
TEXT_QUERY_STYLES = {
    "metadata_brand",
    "semantic_brand_description",
    "metadata_abv",
    "semantic_flavour",
}
IMAGE_QUERY_STYLES = {
    "cropped_bottle_identification",
    "whole_scene_identification",
}
IMAGE_TEXT_QUERY_STYLES = {
    "whole_scene_question",
}


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def test_text_eval_queries_reference_existing_products() -> None:
    products = load_jsonl(CATALOGUE_PATH)
    product_ids = {product["product_id"] for product in products}
    queries = load_jsonl(TEXT_QUERIES_PATH)

    assert 10 <= len(queries) <= 20
    assert len({query["query_id"] for query in queries}) == len(queries)

    for query in queries:
        assert set(query) == {
            "query_id",
            "query_type",
            "query_style",
            "query",
            "label_generation",
            "relevant_product_ids",
            "notes",
        }
        assert query["query_type"] == "text"
        assert query["query_style"] in TEXT_QUERY_STYLES
        assert query["query"].strip()
        assert query["relevant_product_ids"]
        assert query["label_generation"]["method"] == (
            "rule_based_keyword_search_over_product_metadata_and_description"
        )
        assert set(query["relevant_product_ids"]) <= product_ids


def test_image_eval_queries_reference_existing_products_and_images() -> None:
    products = load_jsonl(CATALOGUE_PATH)
    product_ids = {product["product_id"] for product in products}
    queries = load_jsonl(IMAGE_QUERIES_PATH)

    assert len(queries) == 22
    assert len({query["query_id"] for query in queries}) == len(queries)

    for query in queries:
        assert set(query) == {
            "query_id",
            "query_type",
            "query_style",
            "query_image_path",
            "label_generation",
            "relevant_product_ids",
            "notes",
            "source_image_id",
            "screen_reference",
            "whisky_reference",
        }
        assert query["query_type"] == "image"
        assert query["query_style"] in IMAGE_QUERY_STYLES
        assert Path(query["query_image_path"]).exists()
        assert query["relevant_product_ids"]
        assert set(query["relevant_product_ids"]) <= product_ids
        assert query["label_generation"]["method"] == "manual_movie_scene_reference_mapping"


def test_image_text_eval_queries_reference_existing_products_and_images() -> None:
    products = load_jsonl(CATALOGUE_PATH)
    product_ids = {product["product_id"] for product in products}
    queries = load_jsonl(IMAGE_TEXT_QUERIES_PATH)

    assert len(queries) == 11
    assert len({query["query_id"] for query in queries}) == len(queries)

    for query in queries:
        assert set(query) == {
            "query_id",
            "query_type",
            "query_style",
            "query",
            "query_image_path",
            "label_generation",
            "relevant_product_ids",
            "notes",
            "source_image_id",
            "screen_reference",
            "whisky_reference",
        }
        assert query["query_type"] == "image_text"
        assert query["query_style"] in IMAGE_TEXT_QUERY_STYLES
        assert query["query"].strip()
        assert Path(query["query_image_path"]).exists()
        assert query["relevant_product_ids"]
        assert set(query["relevant_product_ids"]) <= product_ids
        assert query["label_generation"]["method"] == "manual_movie_scene_reference_mapping"
