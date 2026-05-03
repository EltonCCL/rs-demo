from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from rs_demo.embeddings import QueryEmbeddingBatch
from rs_demo.queries import EvalQuery
from rs_demo.retrieval import RankedResult


@dataclass(frozen=True)
class QueryEvaluation:
    query_id: str
    relevant_product_ids: list[str]
    retrieved_product_ids: list[str]
    reciprocal_rank: float
    hits: dict[int, bool]


@dataclass(frozen=True)
class RetrievalEvaluationReport:
    query_count: int
    metrics: dict[str, float]
    query_results: list[QueryEvaluation]
    metrics_by_query_style: dict[str, dict[str, float]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "query_count": self.query_count,
            "metrics": self.metrics,
            "metrics_by_query_style": self.metrics_by_query_style,
            "query_results": [
                {
                    "query_id": result.query_id,
                    "relevant_product_ids": result.relevant_product_ids,
                    "retrieved_product_ids": result.retrieved_product_ids,
                    "reciprocal_rank": result.reciprocal_rank,
                    "hits": {f"hit_at_{k}": value for k, value in result.hits.items()},
                }
                for result in self.query_results
            ],
        }


class RetrievalEvaluator:
    def __init__(self, k_values: Iterable[int] = (1, 5, 10)) -> None:
        self.k_values = tuple(sorted(set(k_values)))
        if not self.k_values or any(k <= 0 for k in self.k_values):
            raise ValueError("k_values must contain positive integers")

    def evaluate(
        self,
        queries: Iterable[EvalQuery],
        rankings: dict[str, list[RankedResult]],
    ) -> RetrievalEvaluationReport:
        query_list = list(queries)
        query_results: list[QueryEvaluation] = []
        for query in query_list:
            ranked_results = rankings.get(query.query_id, [])
            retrieved_product_ids = [result.product_id for result in ranked_results]
            relevant_product_ids = set(query.relevant_product_ids)
            first_relevant_rank = next(
                (
                    index
                    for index, product_id in enumerate(retrieved_product_ids, start=1)
                    if product_id in relevant_product_ids
                ),
                None,
            )
            reciprocal_rank = 0.0 if first_relevant_rank is None else 1.0 / first_relevant_rank
            query_results.append(
                QueryEvaluation(
                    query_id=query.query_id,
                    relevant_product_ids=query.relevant_product_ids,
                    retrieved_product_ids=retrieved_product_ids,
                    reciprocal_rank=reciprocal_rank,
                    hits={
                        k: bool(relevant_product_ids.intersection(retrieved_product_ids[:k]))
                        for k in self.k_values
                    },
                )
            )

        metrics = self._aggregate(query_results)
        query_styles = {query.query_id: query.query_style for query in query_list}
        metrics_by_query_style = self._aggregate_by_query_style(query_results, query_styles)
        return RetrievalEvaluationReport(
            query_count=len(query_results),
            metrics=metrics,
            query_results=query_results,
            metrics_by_query_style=metrics_by_query_style,
        )

    def _aggregate(self, query_results: list[QueryEvaluation]) -> dict[str, float]:
        if not query_results:
            return {"mrr": 0.0, **{f"hit_at_{k}": 0.0 for k in self.k_values}}

        metrics = {
            f"hit_at_{k}": sum(result.hits[k] for result in query_results) / len(query_results)
            for k in self.k_values
        }
        metrics["mrr"] = (
            sum(result.reciprocal_rank for result in query_results) / len(query_results)
        )
        return metrics

    def _aggregate_by_query_style(
        self,
        query_results: list[QueryEvaluation],
        query_styles: dict[str, str],
    ) -> dict[str, dict[str, float]]:
        groups: dict[str, list[QueryEvaluation]] = {}
        for result in query_results:
            groups.setdefault(query_styles[result.query_id], []).append(result)
        return {query_style: self._aggregate(results) for query_style, results in groups.items()}


def validate_query_embedding_alignment(
    queries: Iterable[EvalQuery],
    query_batch: QueryEmbeddingBatch,
) -> None:
    expected_query_ids = [query.query_id for query in queries]
    actual_query_ids = query_batch.query_ids
    if expected_query_ids != actual_query_ids:
        raise ValueError(
            "query embedding IDs do not match query file IDs; "
            "rebuild query embeddings before running evaluation"
        )


def write_evaluation_report(
    path: Path | str,
    reports: dict[str, RetrievalEvaluationReport],
) -> None:
    output = {name: report.to_dict() for name, report in reports.items()}
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
