from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


SUPPORTED_QUERY_TYPES = {"text", "image", "image_text"}
SUPPORTED_QUERY_STYLES = {
    "metadata_brand",
    "semantic_brand_description",
    "metadata_abv",
    "semantic_flavour",
    "cropped_bottle_identification",
    "whole_scene_identification",
    "cropped_bottle_question",
    "whole_scene_question",
}


@dataclass(frozen=True)
class EvalQuery:
    query_id: str
    query_type: str
    query_style: str
    relevant_product_ids: list[str]
    query: str | None = None
    query_image_path: str | None = None
    label_generation: dict[str, Any] | None = None
    notes: str = ""
    metadata: dict[str, Any] | None = None

    @classmethod
    def from_record(cls, record: dict[str, Any], base_dir: Path | str = ".") -> EvalQuery:
        query = cls(
            query_id=str(record["query_id"]),
            query_type=str(record["query_type"]),
            query_style=str(record["query_style"]),
            relevant_product_ids=[str(product_id) for product_id in record["relevant_product_ids"]],
            query=record.get("query"),
            query_image_path=record.get("query_image_path"),
            label_generation=record.get("label_generation"),
            notes=str(record.get("notes", "")),
            metadata={
                key: value
                for key, value in record.items()
                if key
                not in {
                    "query_id",
                    "query_type",
                    "query_style",
                    "query",
                    "query_image_path",
                    "label_generation",
                    "relevant_product_ids",
                    "notes",
                }
            },
        )
        query.validate(base_dir=base_dir)
        return query

    def validate(self, base_dir: Path | str = ".") -> None:
        if self.query_type not in SUPPORTED_QUERY_TYPES:
            raise ValueError(f"unsupported query_type: {self.query_type}")
        if self.query_style not in SUPPORTED_QUERY_STYLES:
            raise ValueError(f"unsupported query_style: {self.query_style}")
        if not self.query_id.strip():
            raise ValueError("query_id must not be empty")
        if not self.relevant_product_ids:
            raise ValueError(f"{self.query_id} must have at least one relevant product")

        if self.query_type == "text":
            if not (self.query and self.query.strip()):
                raise ValueError(f"{self.query_id} text query must include query text")
            if self.query_image_path:
                raise ValueError(f"{self.query_id} text query must not include query_image_path")

        if self.query_type == "image":
            self._validate_image_path(base_dir)
            if self.query:
                raise ValueError(f"{self.query_id} image query must not include query text")

        if self.query_type == "image_text":
            if not (self.query and self.query.strip()):
                raise ValueError(f"{self.query_id} image_text query must include query text")
            self._validate_image_path(base_dir)

    def _validate_image_path(self, base_dir: Path | str) -> None:
        if not self.query_image_path:
            raise ValueError(f"{self.query_id} must include query_image_path")
        path = Path(self.query_image_path)
        if not path.is_absolute():
            path = Path(base_dir) / path
        if not path.exists():
            raise ValueError(f"{self.query_id} image path does not exist: {self.query_image_path}")

    def to_record(self) -> dict[str, Any]:
        record: dict[str, Any] = {
            "query_id": self.query_id,
            "query_type": self.query_type,
            "query_style": self.query_style,
            "label_generation": self.label_generation or {},
            "relevant_product_ids": self.relevant_product_ids,
            "notes": self.notes,
        }
        if self.query is not None:
            record["query"] = self.query
        if self.query_image_path is not None:
            record["query_image_path"] = self.query_image_path
        record.update(self.metadata or {})
        return record


class EvalQueryLoader:
    def __init__(self, base_dir: Path | str = ".") -> None:
        self.base_dir = Path(base_dir)

    def load(self, path: Path | str) -> list[EvalQuery]:
        records = read_jsonl(path)
        queries = [EvalQuery.from_record(record, base_dir=self.base_dir) for record in records]
        query_ids = [query.query_id for query in queries]
        if len(set(query_ids)) != len(query_ids):
            raise ValueError(f"duplicate query_id in {path}")
        return queries


def read_jsonl(path: Path | str) -> list[dict[str, Any]]:
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line]


def write_jsonl(path: Path | str, records: Iterable[dict[str, Any]]) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
