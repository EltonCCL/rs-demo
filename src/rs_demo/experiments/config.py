from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ExperimentConfig:
    run_id: str
    dataset_adapter: str
    dataset_options: dict[str, Any]
    provider: str
    provider_options: dict[str, Any]
    output_root: Path = Path("data/experiments/runs")
    dataset_manifest_root: Path = Path("data/experiments/datasets")
    task_ids: tuple[str, ...] = ()
    categories: tuple[str, ...] = ()
    top_k: int = 10
    force: bool = False
    limit_queries: int | None = None
    limit_corpus: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


def load_experiment_config(path: Path | str) -> ExperimentConfig:
    config_path = Path(path)
    payload = tomllib.loads(config_path.read_text(encoding="utf-8"))

    run = _table(payload, "run")
    dataset = _table(payload, "dataset")
    provider = _table(payload, "provider")
    limits = payload.get("limits", {}) or {}
    output = payload.get("output", {}) or {}

    run_id = str(run.get("run_id") or config_path.stem)
    dataset_adapter = _required_str(dataset, "adapter")
    provider_name = _required_str(provider, "name")

    return ExperimentConfig(
        run_id=run_id,
        dataset_adapter=dataset_adapter,
        dataset_options=_options_without(dataset, {"adapter"}),
        provider=provider_name,
        provider_options=_options_without(provider, {"name"}),
        output_root=Path(output.get("runs_root", "data/experiments/runs")),
        dataset_manifest_root=Path(output.get("datasets_root", "data/experiments/datasets")),
        task_ids=tuple(str(value) for value in _as_list(run.get("task_ids"))),
        categories=tuple(str(value) for value in _as_list(run.get("categories"))),
        top_k=int(run.get("top_k", 10)),
        force=bool(run.get("force", False)),
        limit_queries=_optional_int(limits.get("queries")),
        limit_corpus=_optional_int(limits.get("corpus")),
        metadata={
            "config_path": str(config_path),
            "description": run.get("description"),
        },
    )


def _table(payload: dict[str, Any], key: str) -> dict[str, Any]:
    value = payload.get(key)
    if not isinstance(value, dict):
        raise ValueError(f"config must include [{key}] table")
    return value


def _required_str(table: dict[str, Any], key: str) -> str:
    value = table.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"config field {key!r} must be a non-empty string")
    return value


def _options_without(table: dict[str, Any], keys: set[str]) -> dict[str, Any]:
    return {key: _coerce_path_like(value) for key, value in table.items() if key not in keys}


def _coerce_path_like(value: Any) -> Any:
    if isinstance(value, list):
        return [_coerce_path_like(item) for item in value]
    if isinstance(value, dict):
        return {key: _coerce_path_like(item) for key, item in value.items()}
    return value


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    return int(value)
