from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import numpy as np


EMBEDDING_ARRAY_FILES = {
    "text": "text_embeddings.npy",
    "image": "image_embeddings.npy",
    "multimodal": "multimodal_embeddings.npy",
}


@dataclass(frozen=True)
class ProductEmbeddingInput:
    product_id: str
    text: str
    image_path: str | None = None
    metadata: dict[str, Any] | None = None


@dataclass(frozen=True)
class ProductEmbeddingBatch:
    metadata: list[dict[str, Any]]
    text_embeddings: np.ndarray
    image_embeddings: np.ndarray
    multimodal_embeddings: np.ndarray

    @property
    def product_ids(self) -> list[str]:
        return [record["product_id"] for record in self.metadata]


@dataclass(frozen=True)
class QueryEmbeddingInput:
    query_id: str
    query_type: str
    text: str | None = None
    image_path: str | None = None
    metadata: dict[str, Any] | None = None


@dataclass(frozen=True)
class QueryEmbeddingBatch:
    metadata: list[dict[str, Any]]
    embeddings: np.ndarray

    @property
    def query_ids(self) -> list[str]:
        return [record["query_id"] for record in self.metadata]


@dataclass(frozen=True)
class MockEmbeddingConfig:
    input_path: Path = Path("data/extracted/product_parse_sample.jsonl")
    output_dir: Path = Path("data/embeddings/mock")
    dimension: int = 32


@dataclass(frozen=True)
class MockQueryEmbeddingConfig:
    input_path: Path
    output_dir: Path
    dimension: int = 32
    query_base_dir: Path = Path(".")


class MockEmbeddingModel:
    """Deterministic local stand-in for a real embedding provider."""

    def __init__(self, dimension: int = 32, seed: str = "rs-demo-mock-v1") -> None:
        if dimension <= 0:
            raise ValueError("dimension must be positive")
        self.dimension = dimension
        self.seed = seed

    def embed_text(self, text: str) -> np.ndarray:
        return self._hash_to_unit_vector("text", text)

    def embed_image(self, image_path: str | None) -> np.ndarray:
        if not image_path:
            return np.zeros(self.dimension, dtype=np.float32)

        path = Path(image_path)
        content_hash = ""
        if path.exists() and path.is_file():
            content_hash = hashlib.sha256(path.read_bytes()).hexdigest()

        return self._hash_to_unit_vector("image", f"{path.as_posix()}\n{content_hash}")

    def embed_multimodal(self, text: str, image_path: str | None) -> np.ndarray:
        image_marker = image_path or ""
        if image_path and Path(image_path).exists():
            image_marker = hashlib.sha256(Path(image_path).read_bytes()).hexdigest()
        return self._hash_to_unit_vector("multimodal", f"{text}\n---image---\n{image_marker}")

    def _hash_to_unit_vector(self, namespace: str, value: str) -> np.ndarray:
        values: list[float] = []
        counter = 0
        while len(values) < self.dimension:
            digest = hashlib.sha256(
                f"{self.seed}:{namespace}:{counter}:{value}".encode("utf-8")
            ).digest()
            values.extend((byte / 127.5) - 1.0 for byte in digest)
            counter += 1

        vector = np.array(values[: self.dimension], dtype=np.float32)
        norm = np.linalg.norm(vector)
        if norm == 0:
            return vector
        return vector / norm


class ProductEmbeddingBuilder:
    def __init__(self, model: MockEmbeddingModel) -> None:
        self.model = model

    def build(self, inputs: Iterable[ProductEmbeddingInput]) -> ProductEmbeddingBatch:
        records = list(inputs)
        metadata = [self._metadata_for(record) for record in records]

        if not records:
            empty = np.empty((0, self.model.dimension), dtype=np.float32)
            return ProductEmbeddingBatch(
                metadata=[],
                text_embeddings=empty,
                image_embeddings=empty.copy(),
                multimodal_embeddings=empty.copy(),
            )

        text_embeddings = np.vstack([self.model.embed_text(record.text) for record in records])
        image_embeddings = np.vstack([self.model.embed_image(record.image_path) for record in records])
        multimodal_embeddings = np.vstack(
            [self.model.embed_multimodal(record.text, record.image_path) for record in records]
        )

        return ProductEmbeddingBatch(
            metadata=metadata,
            text_embeddings=text_embeddings,
            image_embeddings=image_embeddings,
            multimodal_embeddings=multimodal_embeddings,
        )

    def _metadata_for(self, record: ProductEmbeddingInput) -> dict[str, Any]:
        metadata = dict(record.metadata or {})
        metadata["product_id"] = record.product_id
        metadata["text"] = record.text
        metadata["image_path"] = record.image_path
        return metadata


class QueryEmbeddingBuilder:
    def __init__(self, model: MockEmbeddingModel) -> None:
        self.model = model

    def build(self, inputs: Iterable[QueryEmbeddingInput]) -> QueryEmbeddingBatch:
        records = list(inputs)
        metadata = [self._metadata_for(record) for record in records]

        if not records:
            return QueryEmbeddingBatch(
                metadata=[],
                embeddings=np.empty((0, self.model.dimension), dtype=np.float32),
            )

        embeddings = np.vstack([self._embed(record) for record in records])
        return QueryEmbeddingBatch(metadata=metadata, embeddings=embeddings)

    def _embed(self, record: QueryEmbeddingInput) -> np.ndarray:
        if record.query_type == "text":
            return self.model.embed_text(record.text or "")
        if record.query_type == "image":
            return self.model.embed_image(record.image_path)
        if record.query_type == "image_text":
            return self.model.embed_multimodal(record.text or "", record.image_path)
        raise ValueError(f"unsupported query_type: {record.query_type}")

    def _metadata_for(self, record: QueryEmbeddingInput) -> dict[str, Any]:
        metadata = dict(record.metadata or {})
        metadata["query_id"] = record.query_id
        metadata["query_type"] = record.query_type
        metadata["query"] = record.text
        metadata["query_image_path"] = record.image_path
        return metadata


class NumpyEmbeddingStore:
    def __init__(self, output_dir: Path | str) -> None:
        self.output_dir = Path(output_dir)

    def write(self, batch: ProductEmbeddingBatch) -> None:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        np.save(self.output_dir / EMBEDDING_ARRAY_FILES["text"], batch.text_embeddings)
        np.save(self.output_dir / EMBEDDING_ARRAY_FILES["image"], batch.image_embeddings)
        np.save(self.output_dir / EMBEDDING_ARRAY_FILES["multimodal"], batch.multimodal_embeddings)

        metadata_path = self.output_dir / "metadata.jsonl"
        with metadata_path.open("w", encoding="utf-8") as handle:
            for record in batch.metadata:
                handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")

        manifest = {
            "record_count": len(batch.metadata),
            "dimension": int(batch.text_embeddings.shape[1]),
            "arrays": EMBEDDING_ARRAY_FILES,
        }
        (self.output_dir / "manifest.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    def read(self) -> ProductEmbeddingBatch:
        metadata_path = self.output_dir / "metadata.jsonl"
        metadata = [
            json.loads(line) for line in metadata_path.read_text(encoding="utf-8").splitlines() if line
        ]

        batch = ProductEmbeddingBatch(
            metadata=metadata,
            text_embeddings=np.load(self.output_dir / EMBEDDING_ARRAY_FILES["text"]),
            image_embeddings=np.load(self.output_dir / EMBEDDING_ARRAY_FILES["image"]),
            multimodal_embeddings=np.load(self.output_dir / EMBEDDING_ARRAY_FILES["multimodal"]),
        )
        self._validate(batch)
        return batch

    def _validate(self, batch: ProductEmbeddingBatch) -> None:
        expected_count = len(batch.metadata)
        arrays = [
            batch.text_embeddings,
            batch.image_embeddings,
            batch.multimodal_embeddings,
        ]
        counts = {array.shape[0] for array in arrays}
        dimensions = {array.shape[1] for array in arrays if array.ndim == 2}
        if counts != {expected_count}:
            raise ValueError("embedding row count does not match metadata record count")
        if any(array.ndim != 2 for array in arrays):
            raise ValueError("embedding arrays must be 2D")
        if len(dimensions) != 1:
            raise ValueError("embedding arrays must share the same dimension")


class NumpyQueryEmbeddingStore:
    def __init__(self, output_dir: Path | str) -> None:
        self.output_dir = Path(output_dir)

    def write(self, batch: QueryEmbeddingBatch) -> None:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        np.save(self.output_dir / "embeddings.npy", batch.embeddings)

        metadata_path = self.output_dir / "metadata.jsonl"
        with metadata_path.open("w", encoding="utf-8") as handle:
            for record in batch.metadata:
                handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")

        manifest = {
            "record_count": len(batch.metadata),
            "dimension": int(batch.embeddings.shape[1]) if batch.embeddings.ndim == 2 else None,
            "array": "embeddings.npy",
        }
        (self.output_dir / "manifest.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    def read(self) -> QueryEmbeddingBatch:
        metadata_path = self.output_dir / "metadata.jsonl"
        metadata = [
            json.loads(line) for line in metadata_path.read_text(encoding="utf-8").splitlines() if line
        ]
        batch = QueryEmbeddingBatch(
            metadata=metadata,
            embeddings=np.load(self.output_dir / "embeddings.npy"),
        )
        self._validate(batch)
        return batch

    def _validate(self, batch: QueryEmbeddingBatch) -> None:
        if batch.embeddings.ndim != 2:
            raise ValueError("query embeddings must be a 2D array")
        if batch.embeddings.shape[0] != len(batch.metadata):
            raise ValueError("query embedding row count does not match metadata record count")


class MockEmbeddingPipeline:
    def __init__(self, model_seed: str = "rs-demo-mock-v1") -> None:
        self.model_seed = model_seed

    def run(self, config: MockEmbeddingConfig) -> ProductEmbeddingBatch:
        records = load_product_records(config.input_path)
        inputs = [product_record_to_embedding_input(record) for record in records]
        model = MockEmbeddingModel(dimension=config.dimension, seed=self.model_seed)
        batch = ProductEmbeddingBuilder(model).build(inputs)
        NumpyEmbeddingStore(config.output_dir).write(batch)
        return batch


class MockQueryEmbeddingPipeline:
    def __init__(self, model_seed: str = "rs-demo-mock-v1") -> None:
        self.model_seed = model_seed

    def run(self, config: MockQueryEmbeddingConfig) -> QueryEmbeddingBatch:
        from rs_demo.queries import EvalQueryLoader

        queries = EvalQueryLoader(base_dir=config.query_base_dir).load(config.input_path)
        inputs = [query_record_to_embedding_input(query.to_record()) for query in queries]
        model = MockEmbeddingModel(dimension=config.dimension, seed=self.model_seed)
        batch = QueryEmbeddingBuilder(model).build(inputs)
        NumpyQueryEmbeddingStore(config.output_dir).write(batch)
        return batch


def product_record_to_embedding_input(record: dict[str, Any]) -> ProductEmbeddingInput:
    product_id = str(record["product_id"])
    image_path = record.get("cropped_product_image_path") or record.get("product_image_path")
    text = build_product_text(record)

    metadata_keys = [
        "name",
        "brand_or_distillery",
        "style",
        "region",
        "country",
        "age",
        "abv",
        "source_page",
        "confidence",
        "image_confidence",
    ]
    metadata = {key: record.get(key) for key in metadata_keys if key in record}
    return ProductEmbeddingInput(
        product_id=product_id,
        text=text,
        image_path=str(image_path) if image_path else None,
        metadata=metadata,
    )


def query_record_to_embedding_input(record: dict[str, Any]) -> QueryEmbeddingInput:
    metadata_keys = [
        "query_style",
        "label_generation",
        "relevant_product_ids",
        "notes",
        "source_image_id",
        "screen_reference",
        "whisky_reference",
    ]
    metadata = {key: record.get(key) for key in metadata_keys if key in record}
    image_path = record.get("query_image_path")
    return QueryEmbeddingInput(
        query_id=str(record["query_id"]),
        query_type=str(record["query_type"]),
        text=record.get("query"),
        image_path=str(image_path) if image_path else None,
        metadata=metadata,
    )


def build_product_text(record: dict[str, Any]) -> str:
    fields = [
        ("Name", record.get("name")),
        ("Brand", record.get("brand_or_distillery")),
        ("Style", record.get("style")),
        ("Region", record.get("region")),
        ("Country", record.get("country")),
        ("Age", _format_number(record.get("age"))),
        ("ABV", _format_number(record.get("abv"))),
        ("Product notes", record.get("description")),
        ("Brand context", record.get("brand_description")),
    ]
    return "\n".join(f"{label}: {value}" for label, value in fields if value not in (None, ""))


def load_product_records(path: Path | str) -> list[dict[str, Any]]:
    return load_jsonl_records(path)


def load_jsonl_records(path: Path | str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line.strip():
            records.append(json.loads(line))
    return records


def _format_number(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)
