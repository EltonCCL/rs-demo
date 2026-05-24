from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from rs_demo.rag import (
    GeminiFileSearchClient,
    ProductImageRagCorpusBuilder,
    ProductMultimodalRagCorpusBuilder,
    ProductTextRagCorpusBuilder,
    RagImageCorpusConfig,
    RagProductDocument,
    RagMultimodalCorpusConfig,
    RagQueryResult,
    RagRankedProduct,
    RagStoreRef,
    RagTextCorpusConfig,
    RagTextEvaluationConfig,
    RagTextEvaluationPipeline,
    RagTextStoreConfig,
    RagTextStoreIngestionPipeline,
    RagUploadResult,
    build_rag_text_query_prompt,
    load_rag_documents,
    parse_rag_ranked_products,
)


class FakeFileSearchClient:
    def __init__(self) -> None:
        self.created_store: RagStoreRef | None = None
        self.uploaded_documents: list[RagProductDocument] = []
        self.search_queries: list[str] = []

    def create_store(self, display_name: str, embedding_model: str) -> RagStoreRef:
        self.created_store = RagStoreRef(
            name="fileSearchStores/test-store",
            display_name=display_name,
            embedding_model=embedding_model,
        )
        return self.created_store

    def upload_document(
        self,
        store_name: str,
        document: RagProductDocument,
        wait: bool,
        poll_interval_seconds: float,
        timeout_seconds: float,
    ) -> RagUploadResult:
        self.uploaded_documents.append(document)
        return RagUploadResult(
            product_id=document.product_id,
            file_path=document.path.as_posix(),
            operation_name=f"operations/{document.product_id}",
            done=wait,
        )

    def search_products(
        self,
        store_name: str,
        query_id: str,
        query: str,
        query_type: str,
        image_path: str | None,
        top_k: int,
        model_name: str,
    ) -> RagQueryResult:
        self.search_queries.append(f"{query_type}:{query}:{image_path or ''}")
        return RagQueryResult(
            query_id=query_id,
            query=query,
            raw_text='{"results":[{"rank":1,"product_id":"p001","product_name":"A"}]}',
            ranked_products=[
                RagRankedProduct(product_id="p001", rank=1, product_name="A")
            ],
        )


def test_product_text_rag_corpus_builder_writes_files_and_manifest(tmp_path: Path) -> None:
    catalogue = tmp_path / "products.jsonl"
    catalogue.write_text(
        (
            '{"product_id": "p001", "name": "A", "brand_or_distillery": "Brand A", '
            '"description": "Smoky coastal notes."}\n'
            '{"product_id": "p002", "name": "B", "brand_or_distillery": "Brand B", '
            '"description": "Sweet fruit."}\n'
        ),
        encoding="utf-8",
    )

    documents = ProductTextRagCorpusBuilder().build(
        RagTextCorpusConfig(
            catalogue_path=catalogue,
            output_dir=tmp_path / "corpus",
        )
    )

    assert [document.product_id for document in documents] == ["p001", "p002"]
    first_text = documents[0].path.read_text(encoding="utf-8")
    assert "title: A" in first_text
    assert "product_id: p001" in first_text
    assert "Brand: Brand A" in first_text

    loaded = load_rag_documents(tmp_path / "corpus" / "manifest.jsonl")
    assert [document.product_id for document in loaded] == ["p001", "p002"]
    assert loaded[0].path.exists()


def test_product_multimodal_rag_corpus_builder_writes_pdf_files(tmp_path: Path) -> None:
    catalogue = tmp_path / "products.jsonl"
    catalogue.write_text(
        (
            '{"product_id": "p001", "name": "A", "brand_or_distillery": "Brand A", '
            '"description": "Smoky coastal notes."}\n'
        ),
        encoding="utf-8",
    )

    documents = ProductMultimodalRagCorpusBuilder().build(
        RagMultimodalCorpusConfig(
            catalogue_path=catalogue,
            output_dir=tmp_path / "multimodal",
        )
    )

    assert len(documents) == 1
    assert documents[0].path.suffix == ".pdf"
    assert documents[0].mime_type == "application/pdf"
    assert documents[0].path.exists()
    loaded = load_rag_documents(tmp_path / "multimodal" / "manifest.jsonl")
    assert loaded[0].mime_type == "application/pdf"


def test_product_image_rag_corpus_builder_writes_jpeg_files(tmp_path: Path) -> None:
    source_image = tmp_path / "source.png"
    import fitz

    pixmap = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 12, 12), False)
    pixmap.clear_with(255)
    pixmap.save(source_image)

    catalogue = tmp_path / "products.jsonl"
    catalogue.write_text(
        json.dumps(
            {
                "product_id": "p001",
                "name": "A",
                "brand_or_distillery": "Brand A",
                "cropped_product_image_path": str(source_image),
            }
        )
        + "\n",
        encoding="utf-8",
    )

    documents = ProductImageRagCorpusBuilder().build(
        RagImageCorpusConfig(
            catalogue_path=catalogue,
            output_dir=tmp_path / "image",
        )
    )

    assert len(documents) == 1
    assert documents[0].path.suffix == ".jpg"
    assert documents[0].mime_type == "image/jpeg"
    assert documents[0].metadata["corpus_type"] == "product_image"
    assert documents[0].path.exists()
    loaded = load_rag_documents(tmp_path / "image" / "manifest.jsonl")
    assert loaded[0].mime_type == "image/jpeg"


def test_rag_text_store_ingestion_uploads_manifest_documents(tmp_path: Path) -> None:
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    product_file = corpus / "p001.txt"
    product_file.write_text("title: A\nproduct_id: p001\ntext:\nName: A", encoding="utf-8")
    (corpus / "manifest.jsonl").write_text(
        json.dumps(
            {
                "product_id": "p001",
                "name": "A",
                "path": "p001.txt",
                "metadata": {"product_id": "p001", "name": "A"},
                "char_count": 38,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    client = FakeFileSearchClient()

    manifest = RagTextStoreIngestionPipeline(client=client).run(
        RagTextStoreConfig(
            corpus_manifest_path=corpus / "manifest.jsonl",
            output_path=tmp_path / "store.json",
            display_name="rag_product_text_store",
            sleep_seconds=0,
            poll_interval_seconds=0,
        )
    )

    assert client.created_store is not None
    assert client.uploaded_documents[0].product_id == "p001"
    assert manifest["store_name"] == "fileSearchStores/test-store"
    assert manifest["document_count"] == 1
    assert (tmp_path / "store.json").exists()


def test_rag_store_ingestion_resumes_existing_manifest(tmp_path: Path) -> None:
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    for product_id in ["p001", "p002"]:
        (corpus / f"{product_id}.txt").write_text(
            f"title: {product_id}\nproduct_id: {product_id}",
            encoding="utf-8",
        )
    (corpus / "manifest.jsonl").write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "product_id": "p001",
                        "name": "A",
                        "path": "p001.txt",
                        "metadata": {"product_id": "p001"},
                        "char_count": 20,
                    }
                ),
                json.dumps(
                    {
                        "product_id": "p002",
                        "name": "B",
                        "path": "p002.txt",
                        "metadata": {"product_id": "p002"},
                        "char_count": 20,
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    store_manifest = tmp_path / "store.json"
    store_manifest.write_text(
        json.dumps(
            {
                "store_name": "fileSearchStores/existing",
                "display_name": "existing",
                "embedding_model": "models/gemini-embedding-2",
                "uploads": [
                    {
                        "product_id": "p001",
                        "file_path": str(corpus / "p001.txt"),
                        "operation_name": "operations/p001",
                        "done": False,
                        "error": None,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    client = FakeFileSearchClient()

    manifest = RagTextStoreIngestionPipeline(client=client).run(
        RagTextStoreConfig(
            corpus_manifest_path=corpus / "manifest.jsonl",
            output_path=store_manifest,
            concurrency=2,
            sleep_seconds=0,
        )
    )

    assert client.created_store is None
    assert [document.product_id for document in client.uploaded_documents] == ["p002"]
    assert manifest["store_name"] == "fileSearchStores/existing"
    assert len(manifest["uploads"]) == 2


def test_rag_text_evaluation_pipeline_evaluates_generated_product_ids(tmp_path: Path) -> None:
    catalogue = tmp_path / "products.jsonl"
    catalogue.write_text(
        (
            '{"product_id": "p001", "name": "A", "brand_or_distillery": "Brand A"}\n'
            '{"product_id": "p002", "name": "B", "brand_or_distillery": "Brand B"}\n'
        ),
        encoding="utf-8",
    )
    queries = tmp_path / "queries.jsonl"
    queries.write_text(
        (
            '{"query_id": "q001", "query_type": "text", "query_style": "metadata_brand", '
            '"query": "I want Brand A.", "relevant_product_ids": ["p001"]}\n'
        ),
        encoding="utf-8",
    )
    client = FakeFileSearchClient()

    output = RagTextEvaluationPipeline(client=client).run(
        RagTextEvaluationConfig(
            store_name="fileSearchStores/test-store",
            query_path=queries,
            catalogue_path=catalogue,
            output_path=tmp_path / "report.json",
            top_k=5,
        )
    )

    assert client.search_queries == ["text:I want Brand A.:"]
    assert output.report.metrics["hit_at_1"] == 1.0
    assert output.diagnostics["valid_product_id_rate"] == 1.0
    assert output.raw_results[0].ranked_products[0].product_id == "p001"


def test_rag_evaluation_pipeline_accepts_image_queries(tmp_path: Path) -> None:
    catalogue = tmp_path / "products.jsonl"
    catalogue.write_text(
        '{"product_id": "p001", "name": "A", "brand_or_distillery": "Brand A"}\n',
        encoding="utf-8",
    )
    image = tmp_path / "query.jpg"
    image.write_bytes(b"not-a-real-jpeg-but-not-read-by-fake-client")
    queries = tmp_path / "queries.jsonl"
    queries.write_text(
        json.dumps(
            {
                "query_id": "iq001",
                "query_type": "image",
                "query_style": "cropped_bottle_identification",
                "query_image_path": str(image),
                "relevant_product_ids": ["p001"],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    client = FakeFileSearchClient()

    output = RagTextEvaluationPipeline(client=client).run(
        RagTextEvaluationConfig(
            store_name="fileSearchStores/test-store",
            query_path=queries,
            catalogue_path=catalogue,
            output_path=tmp_path / "report.json",
            report_key="rag_image",
            top_k=5,
        )
    )

    assert client.search_queries == [
        f"image:Find the catalogue whisky product that matches the attached image.:{image}"
    ]
    assert output.to_dict()["rag_image"]["metrics"]["hit_at_1"] == 1.0


def test_parse_rag_ranked_products_accepts_dict_and_drops_duplicates() -> None:
    products = parse_rag_ranked_products(
        '{"results":['
        '{"rank":1,"product_id":"p001","product_name":"A"},'
        '{"rank":2,"product_id":"p001","product_name":"A duplicate"},'
        '{"rank":3,"product_id":"p002","product_name":"B"}'
        "]}",
        top_k=5,
    )

    assert [product.product_id for product in products] == ["p001", "p002"]
    assert products[0].rank == 1


def test_parse_rag_ranked_products_normalizes_document_filenames() -> None:
    products = parse_rag_ranked_products(
        '{"results":['
        '{"rank":1,"product_id":"p001.jpg","product_name":"A"},'
        '{"rank":2,"product_id":"data/rag/product_multimodal_corpus/p002.pdf","product_name":"B"}'
        "]}",
        top_k=5,
    )

    assert [product.product_id for product in products] == ["p001", "p002"]


def test_parse_rag_ranked_products_returns_empty_for_non_json_text() -> None:
    assert parse_rag_ranked_products("I could not find any products.", top_k=5) == []


def test_build_rag_text_query_prompt_instructs_file_search_only() -> None:
    prompt = build_rag_text_query_prompt("I want an Ardbeg whisky.", top_k=5)

    assert "Use only the catalogue records returned by File Search" in prompt
    assert "Return JSON only" in prompt
    assert "I want an Ardbeg whisky." in prompt


def test_gemini_file_search_client_uses_explicit_api_key_without_env_loader() -> None:
    with patch("rs_demo.rag.load_api_key") as load_api_key, patch("rs_demo.rag.genai.Client") as client:
        created = GeminiFileSearchClient(api_key="manual-key")

    assert created.api_key == "manual-key"
    load_api_key.assert_not_called()
    client.assert_called_once_with(api_key="manual-key")
