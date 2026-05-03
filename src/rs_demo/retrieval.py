from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from rs_demo.embeddings import ProductEmbeddingBatch, QueryEmbeddingBatch


@dataclass(frozen=True)
class RankedResult:
    query_id: str
    product_id: str
    rank: int
    score: float
    product_metadata: dict[str, Any]


def cosine_scores(query_embedding: np.ndarray, candidate_embeddings: np.ndarray) -> np.ndarray:
    if query_embedding.ndim != 1:
        raise ValueError("query_embedding must be a 1D vector")
    if candidate_embeddings.ndim != 2:
        raise ValueError("candidate_embeddings must be a 2D matrix")
    if candidate_embeddings.shape[1] != query_embedding.shape[0]:
        raise ValueError("query and candidate embeddings must share the same dimension")

    query_norm = np.linalg.norm(query_embedding)
    candidate_norms = np.linalg.norm(candidate_embeddings, axis=1)
    denominator = candidate_norms * query_norm
    raw_scores = candidate_embeddings @ query_embedding
    return np.divide(
        raw_scores,
        denominator,
        out=np.zeros_like(raw_scores, dtype=np.float32),
        where=denominator != 0,
    )


class ProductRetriever:
    def __init__(self, product_batch: ProductEmbeddingBatch) -> None:
        self.product_batch = product_batch

    def rank_text(self, query_batch: QueryEmbeddingBatch, top_k: int | None = None) -> dict[str, list[RankedResult]]:
        return self.rank(query_batch, self.product_batch.text_embeddings, top_k=top_k)

    def rank_image(self, query_batch: QueryEmbeddingBatch, top_k: int | None = None) -> dict[str, list[RankedResult]]:
        return self.rank(query_batch, self.product_batch.image_embeddings, top_k=top_k)

    def rank_multimodal(
        self, query_batch: QueryEmbeddingBatch, top_k: int | None = None
    ) -> dict[str, list[RankedResult]]:
        return self.rank(query_batch, self.product_batch.multimodal_embeddings, top_k=top_k)

    def rank(
        self,
        query_batch: QueryEmbeddingBatch,
        candidate_embeddings: np.ndarray,
        top_k: int | None = None,
    ) -> dict[str, list[RankedResult]]:
        if candidate_embeddings.shape[0] != len(self.product_batch.metadata):
            raise ValueError("candidate row count must match product metadata count")

        limit = len(self.product_batch.metadata) if top_k is None else min(top_k, len(self.product_batch.metadata))
        rankings: dict[str, list[RankedResult]] = {}
        product_ids = self.product_batch.product_ids

        for query_index, query_id in enumerate(query_batch.query_ids):
            scores = cosine_scores(query_batch.embeddings[query_index], candidate_embeddings)
            order = np.argsort(-scores, kind="stable")[:limit]
            rankings[query_id] = [
                RankedResult(
                    query_id=query_id,
                    product_id=product_ids[product_index],
                    rank=rank,
                    score=float(scores[product_index]),
                    product_metadata=self.product_batch.metadata[product_index],
                )
                for rank, product_index in enumerate(order, start=1)
            ]

        return rankings
