from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import numpy as np

from rs_demo.embeddings import (
    MockEmbeddingConfig,
    MockEmbeddingModel,
    MockEmbeddingPipeline,
    MockQueryEmbeddingConfig,
    MockQueryEmbeddingPipeline,
    NumpyEmbeddingStore,
    NumpyQueryEmbeddingStore,
    ProductEmbeddingBuilder,
    QueryEmbeddingBuilder,
    query_record_to_embedding_input,
    build_product_text,
    product_record_to_embedding_input,
)


class EmbeddingPipelineTests(unittest.TestCase):
    def test_mock_builder_generates_expected_arrays(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            image_path = Path(temp_dir) / "bottle.png"
            image_path.write_bytes(b"fake image")
            records = [
                product_record_to_embedding_input(
                    {
                        "product_id": "p0001-test",
                        "name": "TEST WHISKY",
                        "brand_or_distillery": "TEST",
                        "style": "Single Malt",
                        "description": "Honey and smoke.",
                        "cropped_product_image_path": str(image_path),
                    }
                )
            ]

            batch = ProductEmbeddingBuilder(MockEmbeddingModel(dimension=8)).build(records)

            self.assertEqual(batch.product_ids, ["p0001-test"])
            self.assertEqual(batch.text_embeddings.shape, (1, 8))
            self.assertEqual(batch.image_embeddings.shape, (1, 8))
            self.assertEqual(batch.multimodal_embeddings.shape, (1, 8))
            self.assertAlmostEqual(float(np.linalg.norm(batch.text_embeddings[0])), 1.0, places=5)

    def test_embedding_store_writes_and_reads_numpy_arrays(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            inputs = [
                product_record_to_embedding_input(
                    {
                        "product_id": "p0001-a",
                        "name": "A",
                        "description": "Bright apple.",
                    }
                ),
                product_record_to_embedding_input(
                    {
                        "product_id": "p0002-b",
                        "name": "B",
                        "description": "Dark chocolate.",
                    }
                ),
            ]
            batch = ProductEmbeddingBuilder(MockEmbeddingModel(dimension=6)).build(inputs)
            store = NumpyEmbeddingStore(Path(temp_dir) / "embeddings")

            store.write(batch)
            loaded = store.read()

            self.assertEqual(loaded.product_ids, ["p0001-a", "p0002-b"])
            np.testing.assert_allclose(loaded.text_embeddings, batch.text_embeddings)
            np.testing.assert_allclose(loaded.image_embeddings, batch.image_embeddings)
            np.testing.assert_allclose(loaded.multimodal_embeddings, batch.multimodal_embeddings)

    def test_script_builds_mock_embeddings_from_jsonl(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            input_path = root / "products.jsonl"
            output_dir = root / "mock_embeddings"
            input_path.write_text(
                (
                    '{"product_id": "p0001-a", "name": "A", "description": "Bright apple."}\n'
                    '{"product_id": "p0002-b", "name": "B", "description": "Dark chocolate."}\n'
                ),
                encoding="utf-8",
            )

            MockEmbeddingPipeline().run(
                MockEmbeddingConfig(input_path=input_path, output_dir=output_dir, dimension=5)
            )
            loaded = NumpyEmbeddingStore(output_dir).read()

            self.assertEqual(loaded.product_ids, ["p0001-a", "p0002-b"])
            self.assertEqual(loaded.text_embeddings.shape, (2, 5))
            self.assertTrue((output_dir / "manifest.json").exists())

    def test_query_embedding_store_writes_and_reads_numpy_array(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            image_path = Path(temp_dir) / "query.jpg"
            image_path.write_bytes(b"fake query image")
            inputs = [
                query_record_to_embedding_input(
                    {
                        "query_id": "q001",
                        "query_type": "text",
                        "query_style": "metadata_brand",
                        "query": "I want an Ardbeg whisky.",
                        "relevant_product_ids": ["p0021-ardbeg-10-year-old"],
                    }
                ),
                query_record_to_embedding_input(
                    {
                        "query_id": "q002",
                        "query_type": "image_text",
                        "query_style": "whole_scene_question",
                        "query": "What is the whisky in this image?",
                        "query_image_path": str(image_path),
                        "relevant_product_ids": ["p0021-ardbeg-10-year-old"],
                    }
                ),
            ]
            batch = QueryEmbeddingBuilder(MockEmbeddingModel(dimension=7)).build(inputs)
            store = NumpyQueryEmbeddingStore(Path(temp_dir) / "query_embeddings")

            store.write(batch)
            loaded = store.read()

            self.assertEqual(loaded.query_ids, ["q001", "q002"])
            self.assertEqual(loaded.embeddings.shape, (2, 7))
            np.testing.assert_allclose(loaded.embeddings, batch.embeddings)

    def test_query_embedding_pipeline_builds_from_jsonl(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            image_path = root / "query.jpg"
            image_path.write_bytes(b"fake query image")
            input_path = root / "queries.jsonl"
            output_dir = root / "query_embeddings"
            input_path.write_text(
                (
                    '{"query_id": "q001", "query_type": "image", '
                    '"query_style": "cropped_bottle_identification", '
                    f'"query_image_path": "{image_path}", '
                    '"relevant_product_ids": ["p0001-a"]}\n'
                ),
                encoding="utf-8",
            )

            MockQueryEmbeddingPipeline().run(
                MockQueryEmbeddingConfig(input_path=input_path, output_dir=output_dir, dimension=4)
            )
            loaded = NumpyQueryEmbeddingStore(output_dir).read()

            self.assertEqual(loaded.query_ids, ["q001"])
            self.assertEqual(loaded.embeddings.shape, (1, 4))

    def test_query_embedding_pipeline_validates_query_schema_before_embedding(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            input_path = root / "queries.jsonl"
            output_dir = root / "query_embeddings"
            input_path.write_text(
                (
                    '{"query_id": "q001", "query_type": "image", '
                    '"query_style": "cropped_bottle_identification", '
                    '"query_image_path": "missing.jpg", '
                    '"relevant_product_ids": ["p0001-a"]}\n'
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "image path does not exist"):
                MockQueryEmbeddingPipeline().run(
                    MockQueryEmbeddingConfig(
                        input_path=input_path,
                        output_dir=output_dir,
                        dimension=4,
                        query_base_dir=root,
                    )
                )

    def test_product_text_keeps_structured_fields(self) -> None:
        text = build_product_text(
            {
                "name": "ARDBEG 10-YEAR-OLD",
                "brand_or_distillery": "ARDBEG",
                "style": "Single Malt",
                "region": "Islay",
                "country": "Scotland",
                "age": 10,
                "abv": 46.0,
                "description": "Smoked fish and peat.",
            }
        )

        self.assertIn("Name: ARDBEG 10-YEAR-OLD", text)
        self.assertIn("ABV: 46", text)
        self.assertIn("Product notes: Smoked fish and peat.", text)


if __name__ == "__main__":
    unittest.main()
