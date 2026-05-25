from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from rs_demo.experiments.domain import EmbeddingInput


@dataclass(frozen=True)
class EmbeddingArtifact:
    items: list[EmbeddingInput]
    vectors: np.ndarray
    manifest: dict[str, Any]

    @property
    def ids(self) -> list[str]:
        return [item.id for item in self.items]


class GenericEmbeddingStore:
    def __init__(self, root_dir: Path | str) -> None:
        self.root_dir = Path(root_dir)

    def path_for(
        self,
        *,
        run_id: str,
        dataset_id: str,
        model_id: str,
        split: str,
        view: str,
    ) -> Path:
        safe_model = _safe_path_id(model_id)
        return self.root_dir / run_id / "embeddings" / dataset_id / safe_model / split / view

    def write(
        self,
        path: Path | str,
        *,
        items: list[EmbeddingInput],
        vectors: np.ndarray,
        manifest: dict[str, Any],
    ) -> None:
        output_dir = Path(path)
        output_dir.mkdir(parents=True, exist_ok=True)
        if vectors.ndim != 2:
            raise ValueError("vectors must be a 2D array")
        if vectors.shape[0] != len(items):
            raise ValueError("vector row count must match item count")

        np.save(output_dir / "vectors.npy", vectors.astype(np.float32, copy=False))
        with (output_dir / "items.jsonl").open("w", encoding="utf-8") as handle:
            for item in items:
                handle.write(json.dumps(item.to_dict(), ensure_ascii=False, sort_keys=True) + "\n")

        full_manifest = {
            **manifest,
            "array": "vectors.npy",
            "items": "items.jsonl",
            "record_count": len(items),
            "dimension": int(vectors.shape[1]) if vectors.ndim == 2 else None,
        }
        (output_dir / "manifest.json").write_text(
            json.dumps(full_manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    def read(self, path: Path | str) -> EmbeddingArtifact:
        input_dir = Path(path)
        items_path = input_dir / "items.jsonl"
        manifest_path = input_dir / "manifest.json"
        items = [
            EmbeddingInput.from_dict(json.loads(line))
            for line in items_path.read_text(encoding="utf-8").splitlines()
            if line
        ]
        vectors = np.load(input_dir / "vectors.npy")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        artifact = EmbeddingArtifact(items=items, vectors=vectors, manifest=manifest)
        self._validate(artifact)
        return artifact

    @staticmethod
    def can_reuse(
        path: Path | str,
        expected_ids: list[str],
        dimension: int,
        *,
        expected_items: list[EmbeddingInput] | None = None,
        expected_manifest: dict[str, Any] | None = None,
    ) -> bool:
        input_dir = Path(path)
        if not (input_dir / "vectors.npy").exists() or not (input_dir / "items.jsonl").exists():
            return False
        artifact = GenericEmbeddingStore(input_dir).read(input_dir)
        if artifact.ids != expected_ids:
            return False
        if artifact.vectors.shape != (len(expected_ids), dimension):
            return False
        if expected_items is not None:
            existing_items = [item.to_dict() for item in artifact.items]
            if existing_items != [item.to_dict() for item in expected_items]:
                return False
        if expected_manifest is not None:
            for key, value in expected_manifest.items():
                if artifact.manifest.get(key) != value:
                    return False
        return True

    @staticmethod
    def _validate(artifact: EmbeddingArtifact) -> None:
        if artifact.vectors.ndim != 2:
            raise ValueError("vectors must be a 2D array")
        if artifact.vectors.shape[0] != len(artifact.items):
            raise ValueError("vector row count does not match item count")


def _safe_path_id(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in {"-", "_", "."} else "-" for ch in value)
