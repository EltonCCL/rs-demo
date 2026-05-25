from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RetrievalMetrics:
    query_count: int
    metrics: dict[str, float]
    metrics_by_category: dict[str, dict[str, float]]
    metrics_by_task: dict[str, dict[str, float]]
    query_results: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "query_count": self.query_count,
            "metrics": self.metrics,
            "metrics_by_category": self.metrics_by_category,
            "metrics_by_task": self.metrics_by_task,
            "query_results": self.query_results,
        }


def evaluate_rankings(
    *,
    rankings: dict[str, list[str]],
    qrels: dict[str, list[str]],
    query_categories: dict[str, str],
    query_tasks: dict[str, str] | None = None,
    k_values: tuple[int, ...] = (1, 5, 10),
) -> RetrievalMetrics:
    k_values = tuple(sorted(set(k_values)))
    query_results: list[dict[str, Any]] = []
    for query_id, relevant_ids in qrels.items():
        retrieved_ids = rankings.get(query_id, [])
        relevant_set = set(relevant_ids)
        first_rank = next(
            (
                index
                for index, product_id in enumerate(retrieved_ids, start=1)
                if product_id in relevant_set
            ),
            None,
        )
        result: dict[str, Any] = {
            "query_id": query_id,
            "category": query_categories.get(query_id, "unknown"),
            "task_id": (query_tasks or {}).get(query_id, "unknown"),
            "relevant_ids": relevant_ids,
            "retrieved_ids": retrieved_ids,
            "reciprocal_rank": 0.0 if first_rank is None else 1.0 / first_rank,
        }
        for k in k_values:
            top_k = retrieved_ids[:k]
            hit_count = len(relevant_set.intersection(top_k))
            result[f"hit_at_{k}"] = hit_count > 0
            result[f"precision_at_{k}"] = hit_count / k
            result[f"recall_at_{k}"] = hit_count / len(relevant_set) if relevant_set else 0.0
            result[f"ndcg_at_{k}"] = _ndcg_at_k(top_k, relevant_set, k)
        query_results.append(result)

    metrics = _aggregate(query_results, k_values)
    grouped: dict[str, list[dict[str, Any]]] = {}
    for result in query_results:
        grouped.setdefault(str(result["category"]), []).append(result)
    metrics_by_category = {
        category: _aggregate(results, k_values) for category, results in sorted(grouped.items())
    }
    grouped_tasks: dict[str, list[dict[str, Any]]] = {}
    for result in query_results:
        grouped_tasks.setdefault(str(result["task_id"]), []).append(result)
    metrics_by_task = {
        task_id: _aggregate(results, k_values) for task_id, results in sorted(grouped_tasks.items())
    }
    return RetrievalMetrics(
        query_count=len(query_results),
        metrics=metrics,
        metrics_by_category=metrics_by_category,
        metrics_by_task=metrics_by_task,
        query_results=query_results,
    )


def _aggregate(query_results: list[dict[str, Any]], k_values: tuple[int, ...]) -> dict[str, float]:
    if not query_results:
        metrics = {"mrr": 0.0}
        for k in k_values:
            metrics[f"hit_at_{k}"] = 0.0
            metrics[f"precision_at_{k}"] = 0.0
            metrics[f"recall_at_{k}"] = 0.0
            metrics[f"ndcg_at_{k}"] = 0.0
        return metrics

    metrics = {
        "mrr": sum(float(result["reciprocal_rank"]) for result in query_results)
        / len(query_results)
    }
    for k in k_values:
        metrics[f"hit_at_{k}"] = (
            sum(bool(result[f"hit_at_{k}"]) for result in query_results) / len(query_results)
        )
        metrics[f"precision_at_{k}"] = (
            sum(float(result[f"precision_at_{k}"]) for result in query_results)
            / len(query_results)
        )
        metrics[f"recall_at_{k}"] = (
            sum(float(result[f"recall_at_{k}"]) for result in query_results) / len(query_results)
        )
        metrics[f"ndcg_at_{k}"] = (
            sum(float(result[f"ndcg_at_{k}"]) for result in query_results) / len(query_results)
        )
    return metrics


def _ndcg_at_k(retrieved_ids: list[str], relevant_ids: set[str], k: int) -> float:
    dcg = 0.0
    for index, item_id in enumerate(retrieved_ids[:k], start=1):
        if item_id in relevant_ids:
            dcg += 1.0 / math.log2(index + 1)
    ideal_hits = min(len(relevant_ids), k)
    if ideal_hits == 0:
        return 0.0
    idcg = sum(1.0 / math.log2(index + 1) for index in range(1, ideal_hits + 1))
    return dcg / idcg
