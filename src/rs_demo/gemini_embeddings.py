from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import numpy as np
from google import genai
from google.genai import types

from rs_demo.embeddings import (
    EMBEDDING_ARRAY_FILES,
    NumpyQueryEmbeddingStore,
    ProductEmbeddingBatch,
    QueryEmbeddingBatch,
    build_product_text,
    load_product_records,
    product_record_to_embedding_input,
    query_record_to_embedding_input,
)
from rs_demo.queries import EvalQueryLoader


EmbeddingMode = Literal["text", "image", "multimodal"]


@dataclass(frozen=True)
class GeminiEmbeddingConfig:
    input_path: Path = Path("data/extracted/product_parse_sample.jsonl")
    output_dir: Path = Path("data/embeddings/gemini")
    mode: EmbeddingMode = "text"
    dimension: int = 768
    limit: int | None = None
    max_requests: int | None = None
    sleep_seconds: float = 0.8
    force: bool = False


@dataclass(frozen=True)
class GeminiQueryEmbeddingConfig:
    input_path: Path
    output_dir: Path
    dimension: int = 768
    limit: int | None = None
    max_requests: int | None = None
    sleep_seconds: float = 0.8
    force: bool = False
    query_base_dir: Path = Path(".")


class GeminiEmbeddingModel:
    def __init__(
        self,
        api_key: str | None = None,
        model_name: str = "gemini-embedding-2",
        dimension: int = 768,
    ) -> None:
        if dimension <= 0:
            raise ValueError("dimension must be positive")
        self.model_name = model_name
        self.dimension = dimension
        self.client = genai.Client(api_key=api_key or load_api_key())

    def embed_text(self, text: str) -> np.ndarray:
        return self._embed(text)

    def embed_image(self, image_path: str | None) -> np.ndarray:
        if not image_path:
            raise ValueError("image_path is required for image embedding")
        path = Path(image_path)
        return self._embed([types.Part.from_bytes(data=path.read_bytes(), mime_type=_mime_type(path))])

    def embed_multimodal(self, text: str, image_path: str | None) -> np.ndarray:
        if not image_path:
            raise ValueError("image_path is required for multimodal embedding")
        path = Path(image_path)
        return self._embed(
            [
                text,
                types.Part.from_bytes(data=path.read_bytes(), mime_type=_mime_type(path)),
            ]
        )

    def _embed(self, contents: str | list[Any]) -> np.ndarray:
        response = self.client.models.embed_content(
            model=self.model_name,
            contents=contents,
            config=types.EmbedContentConfig(output_dimensionality=self.dimension),
        )
        return np.array(response.embeddings[0].values, dtype=np.float32)


class GeminiProductEmbeddingPipeline:
    def __init__(self, model: GeminiEmbeddingModel | None = None) -> None:
        self.model = model

    def run(self, config: GeminiEmbeddingConfig) -> ProductEmbeddingBatch:
        records = load_product_records(config.input_path)
        if config.limit is not None:
            records = records[: config.limit]
        inputs = [product_record_to_embedding_input(record) for record in records]
        metadata = [_product_metadata(record) for record in records]
        model = self.model or GeminiEmbeddingModel(dimension=config.dimension)
        cache_dir = config.output_dir / "cache" / "products" / config.mode

        vectors = run_cached_embeddings(
            ids=[record.product_id for record in inputs],
            cache_dir=cache_dir,
            dimension=config.dimension,
            embed_one=lambda index: _embed_product(model, config.mode, inputs[index], records[index]),
            max_requests=config.max_requests,
            sleep_seconds=config.sleep_seconds,
            force=config.force,
        )

        batch = _read_or_create_product_batch(config.output_dir, metadata, config.dimension)
        _assign_product_mode(batch, config.mode, vectors)
        _write_product_batch(config.output_dir, batch, completed_mode=config.mode)
        return batch


class GeminiQueryEmbeddingPipeline:
    def __init__(self, model: GeminiEmbeddingModel | None = None) -> None:
        self.model = model

    def run(self, config: GeminiQueryEmbeddingConfig) -> QueryEmbeddingBatch:
        queries = EvalQueryLoader(base_dir=config.query_base_dir).load(config.input_path)
        if config.limit is not None:
            queries = queries[: config.limit]
        inputs = [query_record_to_embedding_input(query.to_record()) for query in queries]
        model = self.model or GeminiEmbeddingModel(dimension=config.dimension)
        query_type = inputs[0].query_type if inputs else "empty"
        cache_dir = config.output_dir / "cache" / query_type

        vectors = run_cached_embeddings(
            ids=[record.query_id for record in inputs],
            cache_dir=cache_dir,
            dimension=config.dimension,
            embed_one=lambda index: _embed_query(model, inputs[index]),
            max_requests=config.max_requests,
            sleep_seconds=config.sleep_seconds,
            force=config.force,
        )
        batch = QueryEmbeddingBatch(
            metadata=[_query_metadata(record) for record in inputs],
            embeddings=vectors,
        )
        NumpyQueryEmbeddingStore(config.output_dir).write(batch)
        return batch


def run_cached_embeddings(
    ids: list[str],
    cache_dir: Path,
    dimension: int,
    embed_one: Any,
    max_requests: int | None = None,
    sleep_seconds: float = 0.8,
    force: bool = False,
) -> np.ndarray:
    cache_dir.mkdir(parents=True, exist_ok=True)
    vectors: list[np.ndarray] = []
    requests_made = 0

    for index, record_id in enumerate(ids):
        cache_path = cache_dir / f"{record_id}.npy"
        if cache_path.exists() and not force:
            vector = np.load(cache_path)
        else:
            if max_requests is not None and requests_made >= max_requests:
                raise RuntimeError(f"request budget exhausted after {requests_made} new embeddings")
            vector = np.asarray(embed_one(index), dtype=np.float32)
            if vector.shape != (dimension,):
                raise ValueError(f"{record_id} embedding shape {vector.shape} != ({dimension},)")
            np.save(cache_path, vector)
            requests_made += 1
            if sleep_seconds > 0:
                time.sleep(sleep_seconds)
        vectors.append(vector)

    if not vectors:
        return np.empty((0, dimension), dtype=np.float32)
    return np.vstack(vectors)


def load_api_key(env_path: Path = Path(".env")) -> str:
    load_env_file(env_path)
    api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GOOGLE_API_KEY or GEMINI_API_KEY must be set")
    return api_key


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _embed_product(
    model: GeminiEmbeddingModel,
    mode: EmbeddingMode,
    record: Any,
    raw_record: dict[str, Any],
) -> np.ndarray:
    if mode == "text":
        return model.embed_text(_format_product_document(raw_record))
    if mode == "image":
        return model.embed_image(record.image_path)
    if mode == "multimodal":
        return model.embed_multimodal(_format_product_document(raw_record), record.image_path)
    raise ValueError(f"unsupported embedding mode: {mode}")


def _embed_query(model: GeminiEmbeddingModel, record: Any) -> np.ndarray:
    if record.query_type == "text":
        return model.embed_text(f"task: search result | query: {record.text or ''}")
    if record.query_type == "image":
        return model.embed_image(record.image_path)
    if record.query_type == "image_text":
        return model.embed_multimodal(record.text or "", record.image_path)
    raise ValueError(f"unsupported query_type: {record.query_type}")


def _format_product_document(record: dict[str, Any]) -> str:
    name = record.get("name") or record.get("product_id") or "unknown product"
    return f"title: {name} | text: {build_product_text(record)}"


def _read_or_create_product_batch(
    output_dir: Path,
    metadata: list[dict[str, Any]],
    dimension: int,
) -> ProductEmbeddingBatch:
    count = len(metadata)
    arrays = {}
    for mode, filename in EMBEDDING_ARRAY_FILES.items():
        path = output_dir / filename
        if path.exists():
            array = np.load(path)
            if array.shape != (count, dimension):
                raise ValueError(f"existing {filename} shape {array.shape} does not match current input")
            arrays[mode] = array
        else:
            arrays[mode] = np.zeros((count, dimension), dtype=np.float32)

    metadata_path = output_dir / "metadata.jsonl"
    if metadata_path.exists():
        existing_ids = [
            json.loads(line)["product_id"]
            for line in metadata_path.read_text(encoding="utf-8").splitlines()
            if line
        ]
        current_ids = [record["product_id"] for record in metadata]
        if existing_ids != current_ids:
            raise ValueError("existing Gemini product embeddings do not match current product order")

    return ProductEmbeddingBatch(
        metadata=metadata,
        text_embeddings=arrays["text"],
        image_embeddings=arrays["image"],
        multimodal_embeddings=arrays["multimodal"],
    )


def _assign_product_mode(
    batch: ProductEmbeddingBatch,
    mode: EmbeddingMode,
    vectors: np.ndarray,
) -> None:
    if mode == "text":
        batch.text_embeddings[:] = vectors
        return
    if mode == "image":
        batch.image_embeddings[:] = vectors
        return
    if mode == "multimodal":
        batch.multimodal_embeddings[:] = vectors
        return
    raise ValueError(f"unsupported embedding mode: {mode}")


def _write_product_batch(
    output_dir: Path,
    batch: ProductEmbeddingBatch,
    completed_mode: EmbeddingMode,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    np.save(output_dir / EMBEDDING_ARRAY_FILES["text"], batch.text_embeddings)
    np.save(output_dir / EMBEDDING_ARRAY_FILES["image"], batch.image_embeddings)
    np.save(output_dir / EMBEDDING_ARRAY_FILES["multimodal"], batch.multimodal_embeddings)
    with (output_dir / "metadata.jsonl").open("w", encoding="utf-8") as handle:
        for record in batch.metadata:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")

    manifest_path = output_dir / "manifest.json"
    existing: dict[str, Any] = {}
    if manifest_path.exists():
        existing = json.loads(manifest_path.read_text(encoding="utf-8"))
    completed_modes = sorted(set(existing.get("completed_modes", [])) | {completed_mode})
    manifest = {
        "provider": "google",
        "model": "gemini-embedding-2",
        "record_count": len(batch.metadata),
        "dimension": int(batch.text_embeddings.shape[1]),
        "arrays": EMBEDDING_ARRAY_FILES,
        "completed_modes": completed_modes,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _product_metadata(record: dict[str, Any]) -> dict[str, Any]:
    embedded = product_record_to_embedding_input(record)
    return (embedded.metadata or {}) | {
        "product_id": embedded.product_id,
        "text": embedded.text,
        "image_path": embedded.image_path,
    }


def _query_metadata(record: Any) -> dict[str, Any]:
    metadata = dict(record.metadata or {})
    metadata["query_id"] = record.query_id
    metadata["query_type"] = record.query_type
    metadata["query"] = record.text
    metadata["query_image_path"] = record.image_path
    return metadata


def _mime_type(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if suffix == ".png":
        return "image/png"
    if suffix == ".webp":
        return "image/webp"
    raise ValueError(f"unsupported image type: {path}")
