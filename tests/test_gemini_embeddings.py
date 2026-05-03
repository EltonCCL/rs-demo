from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import numpy as np

from rs_demo.embeddings import NumpyEmbeddingStore, NumpyQueryEmbeddingStore
from rs_demo.gemini_embeddings import (
    GeminiEmbeddingConfig,
    GeminiProductEmbeddingPipeline,
    GeminiQueryEmbeddingConfig,
    GeminiQueryEmbeddingPipeline,
)


class FakeGeminiModel:
    def __init__(self, dimension: int = 4) -> None:
        self.dimension = dimension
        self.text_calls = 0

    def embed_text(self, text: str) -> np.ndarray:
        self.text_calls += 1
        value = float(self.text_calls)
        return np.full(self.dimension, value, dtype=np.float32)

    def embed_image(self, image_path: str | None) -> np.ndarray:
        raise AssertionError("image embedding should not be called")

    def embed_multimodal(self, text: str, image_path: str | None) -> np.ndarray:
        raise AssertionError("multimodal embedding should not be called")


class GeminiEmbeddingPipelineTests(unittest.TestCase):
    def test_product_text_pipeline_writes_and_reuses_cached_embeddings(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            input_path = root / "products.jsonl"
            output_dir = root / "gemini"
            input_path.write_text(
                (
                    '{"product_id": "p001", "name": "A", "description": "Apple."}\n'
                    '{"product_id": "p002", "name": "B", "description": "Smoke."}\n'
                ),
                encoding="utf-8",
            )
            model = FakeGeminiModel(dimension=4)

            GeminiProductEmbeddingPipeline(model=model).run(
                GeminiEmbeddingConfig(
                    input_path=input_path,
                    output_dir=output_dir,
                    mode="text",
                    dimension=4,
                    sleep_seconds=0,
                )
            )
            loaded = NumpyEmbeddingStore(output_dir).read()

            self.assertEqual(model.text_calls, 2)
            self.assertEqual(loaded.product_ids, ["p001", "p002"])
            np.testing.assert_allclose(loaded.text_embeddings[0], np.ones(4, dtype=np.float32))

            GeminiProductEmbeddingPipeline(model=model).run(
                GeminiEmbeddingConfig(
                    input_path=input_path,
                    output_dir=output_dir,
                    mode="text",
                    dimension=4,
                    sleep_seconds=0,
                )
            )

            self.assertEqual(model.text_calls, 2)

    def test_query_text_pipeline_writes_query_store(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            input_path = root / "queries.jsonl"
            output_dir = root / "query_embeddings"
            input_path.write_text(
                (
                    '{"query_id": "q001", "query_type": "text", "query_style": "metadata_brand", '
                    '"query": "I want A.", "relevant_product_ids": ["p001"]}\n'
                ),
                encoding="utf-8",
            )
            model = FakeGeminiModel(dimension=4)

            GeminiQueryEmbeddingPipeline(model=model).run(
                GeminiQueryEmbeddingConfig(
                    input_path=input_path,
                    output_dir=output_dir,
                    dimension=4,
                    sleep_seconds=0,
                )
            )
            loaded = NumpyQueryEmbeddingStore(output_dir).read()

            self.assertEqual(model.text_calls, 1)
            self.assertEqual(loaded.query_ids, ["q001"])
            self.assertEqual(loaded.embeddings.shape, (1, 4))


if __name__ == "__main__":
    unittest.main()
