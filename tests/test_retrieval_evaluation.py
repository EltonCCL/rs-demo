from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import numpy as np

from rs_demo.embeddings import ProductEmbeddingBatch, QueryEmbeddingBatch
from rs_demo.evaluation import RetrievalEvaluator, validate_query_embedding_alignment
from rs_demo.queries import EvalQuery, EvalQueryLoader
from rs_demo.retrieval import ProductRetriever, cosine_scores


class RetrievalEvaluationTests(unittest.TestCase):
    def test_cosine_scores_rank_nearest_vector_first(self) -> None:
        scores = cosine_scores(
            np.array([1.0, 0.0], dtype=np.float32),
            np.array([[0.0, 1.0], [1.0, 0.0]], dtype=np.float32),
        )

        self.assertEqual(int(np.argmax(scores)), 1)
        self.assertAlmostEqual(float(scores[1]), 1.0, places=6)

    def test_retriever_and_evaluator_report_hits(self) -> None:
        products = ProductEmbeddingBatch(
            metadata=[
                {"product_id": "p001", "name": "A"},
                {"product_id": "p002", "name": "B"},
            ],
            text_embeddings=np.array([[1.0, 0.0], [0.0, 1.0]], dtype=np.float32),
            image_embeddings=np.array([[1.0, 0.0], [0.0, 1.0]], dtype=np.float32),
            multimodal_embeddings=np.array([[1.0, 0.0], [0.0, 1.0]], dtype=np.float32),
        )
        queries = QueryEmbeddingBatch(
            metadata=[{"query_id": "q001", "query_type": "text"}],
            embeddings=np.array([[0.0, 1.0]], dtype=np.float32),
        )

        rankings = ProductRetriever(products).rank_text(queries, top_k=2)
        report = RetrievalEvaluator(k_values=(1, 2)).evaluate(
            [
                EvalQuery(
                    query_id="q001",
                    query_type="text",
                    query_style="metadata_brand",
                    query="I want B.",
                    relevant_product_ids=["p002"],
                )
            ],
            rankings,
        )

        self.assertEqual(rankings["q001"][0].product_id, "p002")
        self.assertEqual(report.metrics["hit_at_1"], 1.0)
        self.assertEqual(report.metrics["mrr"], 1.0)
        self.assertEqual(report.metrics_by_query_style["metadata_brand"]["hit_at_1"], 1.0)

    def test_eval_query_loader_validates_image_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            image_path = root / "query.jpg"
            image_path.write_bytes(b"fake image")
            query_path = root / "queries.jsonl"
            query_path.write_text(
                (
                    '{"query_id": "iq001", "query_type": "image", '
                    '"query_style": "cropped_bottle_identification", '
                    f'"query_image_path": "{image_path}", '
                    '"relevant_product_ids": ["p001"]}\n'
                ),
                encoding="utf-8",
            )

            queries = EvalQueryLoader().load(query_path)

            self.assertEqual(queries[0].query_id, "iq001")

    def test_validate_query_embedding_alignment_rejects_stale_embeddings(self) -> None:
        queries = [
            EvalQuery(
                query_id="q001",
                query_type="text",
                query_style="metadata_brand",
                query="I want A.",
                relevant_product_ids=["p001"],
            )
        ]
        query_batch = QueryEmbeddingBatch(
            metadata=[{"query_id": "q999", "query_type": "text"}],
            embeddings=np.array([[1.0, 0.0]], dtype=np.float32),
        )

        with self.assertRaisesRegex(ValueError, "rebuild query embeddings"):
            validate_query_embedding_alignment(queries, query_batch)


if __name__ == "__main__":
    unittest.main()
