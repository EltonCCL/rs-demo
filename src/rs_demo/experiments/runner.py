from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from rs_demo.experiments.adapters import build_dataset_adapter
from rs_demo.experiments.config import ExperimentConfig
from rs_demo.experiments.domain import RetrievalDataset, RetrievalItem, TaskSpec
from rs_demo.experiments.metrics import RetrievalMetrics, evaluate_rankings
from rs_demo.experiments.providers import EmbeddingProvider, build_provider
from rs_demo.experiments.store import EmbeddingArtifact, GenericEmbeddingStore


@dataclass(frozen=True)
class ExperimentRunResult:
    run_id: str
    run_dir: Path
    dataset_id: str
    model_id: str
    metrics: RetrievalMetrics
    manifest: dict[str, Any]


class ExperimentRunner:
    def __init__(
        self,
        config: ExperimentConfig,
        provider: EmbeddingProvider | None = None,
        dataset: RetrievalDataset | None = None,
    ) -> None:
        self.config = config
        self.provider = provider or build_provider(config.provider, config.provider_options)
        self.dataset = dataset
        self.store = GenericEmbeddingStore(config.output_root)

    def run(self) -> ExperimentRunResult:
        start = time.time()
        dataset = self.dataset or self._load_dataset()
        task_specs = self._select_tasks(dataset.task_specs)
        if not task_specs:
            raise ValueError("experiment selected no tasks")

        run_dir = self.config.output_root / self.config.run_id
        run_dir.mkdir(parents=True, exist_ok=True)

        artifacts, cache_summary = self._embed_required_views(dataset, task_specs)
        rankings, score_rows = self._rank_tasks(dataset, task_specs, artifacts)
        metrics = evaluate_rankings(
            rankings=rankings,
            qrels={query_id: dataset.qrels[query_id] for query_id in rankings},
            query_categories=_query_categories(task_specs),
            query_tasks=_query_tasks(task_specs),
            k_values=tuple(sorted({k for task in task_specs for k in task.metrics})),
        )

        self._write_rankings(run_dir / "rankings.jsonl", score_rows)
        (run_dir / "metrics.json").write_text(
            json.dumps(metrics.to_dict(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        self._write_dataset_manifest(dataset)
        manifest = self._run_manifest(dataset, task_specs, cache_summary, time.time() - start)
        (run_dir / "manifest.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return ExperimentRunResult(
            run_id=self.config.run_id,
            run_dir=run_dir,
            dataset_id=dataset.dataset_id,
            model_id=self.provider.model_id,
            metrics=metrics,
            manifest=manifest,
        )

    def _load_dataset(self) -> RetrievalDataset:
        adapter = build_dataset_adapter(self.config.dataset_adapter, self.config.dataset_options)
        dataset = adapter.load(
            limit_queries=self.config.limit_queries,
            limit_corpus=self.config.limit_corpus,
        )
        dataset.validate()
        return dataset

    def _select_tasks(self, task_specs: list[TaskSpec]) -> list[TaskSpec]:
        selected = list(task_specs)
        if self.config.task_ids:
            selected = [task for task in selected if task.task_id in self.config.task_ids]
        if self.config.categories:
            selected = [task for task in selected if task.category in self.config.categories]
        return selected

    def _embed_required_views(
        self,
        dataset: RetrievalDataset,
        task_specs: list[TaskSpec],
    ) -> tuple[dict[tuple[str, str], EmbeddingArtifact], dict[str, int]]:
        artifacts: dict[tuple[str, str], EmbeddingArtifact] = {}
        cache_summary = {"reused": 0, "created": 0}
        query_by_id = dataset.queries_by_id
        corpus_by_id = dataset.corpus_by_id

        for split, view, items in self._required_item_groups(task_specs, query_by_id, corpus_by_id):
            inputs = [item.as_embedding_input(view) for item in items]
            path = self.store.path_for(
                run_id=self.config.run_id,
                dataset_id=dataset.dataset_id,
                model_id=self.provider.model_id,
                split=split,
                view=view,
            )
            expected_ids = [item.id for item in inputs]
            embedding_manifest = self._embedding_manifest(dataset, split, view)
            if (
                not self.config.force
                and path.exists()
                and GenericEmbeddingStore.can_reuse(
                    path,
                    expected_ids,
                    self.provider.dimension,
                    expected_items=inputs,
                    expected_manifest=embedding_manifest,
                )
            ):
                artifact = self.store.read(path)
                cache_summary["reused"] += 1
            else:
                vectors = self.provider.encode_batch(inputs)
                self.store.write(
                    path,
                    items=inputs,
                    vectors=vectors,
                    manifest=embedding_manifest,
                )
                artifact = self.store.read(path)
                cache_summary["created"] += 1
            artifacts[(split, view)] = artifact
        return artifacts, cache_summary

    def _required_item_groups(
        self,
        task_specs: list[TaskSpec],
        query_by_id: dict[str, RetrievalItem],
        corpus_by_id: dict[str, RetrievalItem],
    ) -> list[tuple[str, str, list[RetrievalItem]]]:
        groups: dict[tuple[str, str], dict[str, RetrievalItem]] = {}
        for task in task_specs:
            query_group = groups.setdefault(("queries", task.query_view), {})
            for query_id in task.query_ids:
                query_group.setdefault(query_id, query_by_id[query_id])

            corpus_group = groups.setdefault(("corpus", task.corpus_view), {})
            corpus_ids = task.corpus_ids or list(corpus_by_id)
            for corpus_id in corpus_ids:
                corpus_group.setdefault(corpus_id, corpus_by_id[corpus_id])

        return [
            (split, view, list(items.values()))
            for (split, view), items in sorted(groups.items())
        ]

    def _rank_tasks(
        self,
        dataset: RetrievalDataset,
        task_specs: list[TaskSpec],
        artifacts: dict[tuple[str, str], EmbeddingArtifact],
    ) -> tuple[dict[str, list[str]], list[dict[str, Any]]]:
        rankings: dict[str, list[str]] = {}
        score_rows: list[dict[str, Any]] = []
        for task in task_specs:
            query_artifact = artifacts[("queries", task.query_view)]
            corpus_artifact = artifacts[("corpus", task.corpus_view)]
            query_index = {item.id: index for index, item in enumerate(query_artifact.items)}
            corpus_index = {item.id: index for index, item in enumerate(corpus_artifact.items)}

            for query_id in task.query_ids:
                if query_id not in dataset.qrels:
                    continue
                candidate_ids = dataset.candidate_ids.get(query_id) or task.corpus_ids or corpus_artifact.ids
                candidate_indices = [
                    corpus_index[item_id] for item_id in candidate_ids if item_id in corpus_index
                ]
                if not candidate_indices:
                    continue
                candidate_matrix = corpus_artifact.vectors[candidate_indices]
                ranked_candidate_ids = [corpus_artifact.ids[index] for index in candidate_indices]
                top_k = min(max(task.metrics), self.config.top_k, len(ranked_candidate_ids))
                query_vector = query_artifact.vectors[query_index[query_id]]
                scores = _similarity_scores(query_vector, candidate_matrix, task.similarity)
                order = np.argsort(-scores, kind="stable")[:top_k]
                ranked_ids = [ranked_candidate_ids[index] for index in order]
                rankings[query_id] = ranked_ids
                for rank, local_index in enumerate(order, start=1):
                    score_rows.append(
                        {
                            "task_id": task.task_id,
                            "category": task.category,
                            "query_id": query_id,
                            "corpus_id": ranked_candidate_ids[local_index],
                            "rank": rank,
                            "score": float(scores[local_index]),
                            "relevant": ranked_candidate_ids[local_index] in dataset.qrels[query_id],
                            "candidate_count": len(ranked_candidate_ids),
                        }
                    )
        return rankings, score_rows

    def _write_rankings(self, path: Path, score_rows: list[dict[str, Any]]) -> None:
        with path.open("w", encoding="utf-8") as handle:
            for row in score_rows:
                handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")

    def _write_dataset_manifest(self, dataset: RetrievalDataset) -> None:
        out_dir = self.config.dataset_manifest_root / dataset.dataset_id
        out_dir.mkdir(parents=True, exist_ok=True)
        manifest = {
            "dataset_id": dataset.dataset_id,
            "metadata": dataset.metadata,
            "corpus_count": len(dataset.corpus),
            "query_count": len(dataset.queries),
            "qrel_count": len(dataset.qrels),
            "candidate_pool_count": len(dataset.candidate_ids),
            "tasks": [
                {
                    "task_id": task.task_id,
                    "category": task.category,
                    "query_view": task.query_view,
                    "corpus_view": task.corpus_view,
                    "query_count": len(task.query_ids),
                    "corpus_count": None if task.corpus_ids is None else len(task.corpus_ids),
                }
                for task in dataset.task_specs
            ],
        }
        (out_dir / "manifest.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    def _run_manifest(
        self,
        dataset: RetrievalDataset,
        task_specs: list[TaskSpec],
        cache_summary: dict[str, int],
        elapsed_seconds: float,
    ) -> dict[str, Any]:
        return {
            "run_id": self.config.run_id,
            "dataset_id": dataset.dataset_id,
            "dataset_adapter": self.config.dataset_adapter,
            "dataset_options": self.config.dataset_options,
            "provider": self.config.provider,
            "provider_options": self.config.provider_options,
            "model_id": self.provider.model_id,
            "dimension": self.provider.dimension,
            "normalization": self.provider.normalization,
            "task_ids": [task.task_id for task in task_specs],
            "categories": sorted({task.category for task in task_specs}),
            "top_k": self.config.top_k,
            "candidate_pool_count": len(dataset.candidate_ids),
            "cache": cache_summary,
            "elapsed_seconds": elapsed_seconds,
            "metadata": self.config.metadata,
        }

    def _embedding_manifest(self, dataset: RetrievalDataset, split: str, view: str) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "dataset_id": dataset.dataset_id,
            "provider": self.config.provider,
            "provider_options": self.config.provider_options,
            "model_id": self.provider.model_id,
            "normalization": self.provider.normalization,
            "split": split,
            "view": view,
        }


def _similarity_scores(query_vector: np.ndarray, candidates: np.ndarray, similarity: str) -> np.ndarray:
    if similarity == "dot":
        return candidates @ query_vector
    if similarity != "cosine":
        raise ValueError(f"unsupported similarity: {similarity}")
    query_norm = np.linalg.norm(query_vector)
    candidate_norms = np.linalg.norm(candidates, axis=1)
    denominator = candidate_norms * query_norm
    raw_scores = candidates @ query_vector
    return np.divide(
        raw_scores,
        denominator,
        out=np.zeros_like(raw_scores, dtype=np.float32),
        where=denominator != 0,
    )


def _query_categories(task_specs: list[TaskSpec]) -> dict[str, str]:
    categories: dict[str, str] = {}
    for task in task_specs:
        for query_id in task.query_ids:
            categories[query_id] = task.category
    return categories


def _query_tasks(task_specs: list[TaskSpec]) -> dict[str, str]:
    tasks: dict[str, str] = {}
    for task in task_specs:
        for query_id in task.query_ids:
            tasks[query_id] = task.task_id
    return tasks
