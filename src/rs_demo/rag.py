from __future__ import annotations

import json
import hashlib
import time
import textwrap
import urllib.error
import urllib.request
import unicodedata
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from google import genai
from google.genai import types

from rs_demo.embeddings import build_product_text, load_product_records
from rs_demo.evaluation import RetrievalEvaluationReport, RetrievalEvaluator
from rs_demo.gemini_embeddings import load_api_key
from rs_demo.queries import EvalQueryLoader
from rs_demo.retrieval import RankedResult


DEFAULT_FILE_SEARCH_EMBEDDING_MODEL = "models/gemini-embedding-2"
DEFAULT_RAG_GENERATION_MODEL = "gemini-2.5-flash-lite"


@dataclass(frozen=True)
class RagProductDocument:
    product_id: str
    name: str
    path: Path
    metadata: dict[str, str]
    char_count: int
    mime_type: str = "text/plain"
    byte_count: int = 0

    def to_manifest_record(self, root: Path) -> dict[str, Any]:
        return {
            "product_id": self.product_id,
            "name": self.name,
            "path": self.path.relative_to(root).as_posix(),
            "metadata": self.metadata,
            "char_count": self.char_count,
            "mime_type": self.mime_type,
            "byte_count": self.byte_count or self.path.stat().st_size,
            "sha256": _file_sha256(self.path),
        }


@dataclass(frozen=True)
class RagTextCorpusConfig:
    catalogue_path: Path = Path("data/extracted/product_parse_sample.jsonl")
    output_dir: Path = Path("data/rag/product_text_corpus")
    manifest_path: Path | None = None
    limit: int | None = None


@dataclass(frozen=True)
class RagMultimodalCorpusConfig:
    catalogue_path: Path = Path("data/extracted/product_parse_sample.jsonl")
    output_dir: Path = Path("data/rag/product_multimodal_corpus")
    manifest_path: Path | None = None
    limit: int | None = None


@dataclass(frozen=True)
class RagImageCorpusConfig:
    catalogue_path: Path = Path("data/extracted/product_parse_sample.jsonl")
    output_dir: Path = Path("data/rag/product_image_corpus")
    manifest_path: Path | None = None
    limit: int | None = None


@dataclass(frozen=True)
class RagTextStoreConfig:
    corpus_manifest_path: Path = Path("data/rag/product_text_corpus/manifest.jsonl")
    output_path: Path = Path("data/rag/rag_product_text_store.json")
    display_name: str = "rag_product_text_store"
    store_name: str | None = None
    embedding_model: str = DEFAULT_FILE_SEARCH_EMBEDDING_MODEL
    limit: int | None = None
    wait: bool = True
    poll_interval_seconds: float = 5.0
    timeout_seconds: float = 600.0
    sleep_seconds: float = 0.5
    concurrency: int = 1
    resume: bool = True
    progress_every: int = 25


@dataclass(frozen=True)
class RagTextEvaluationConfig:
    store_name: str
    query_path: Path = Path("data/eval/text_queries.jsonl")
    catalogue_path: Path = Path("data/extracted/product_parse_sample.jsonl")
    output_path: Path = Path("data/eval/gemini_rag_text_report.json")
    report_key: str = "rag_text"
    top_k: int = 5
    model_name: str = DEFAULT_RAG_GENERATION_MODEL
    query_base_dir: Path = Path(".")
    sleep_seconds: float = 0.0
    limit: int | None = None
    resume: bool = True
    max_retries: int = 2
    retry_sleep_seconds: float = 10.0
    continue_on_error: bool = False


@dataclass(frozen=True)
class RagStoreRef:
    name: str
    display_name: str
    embedding_model: str


@dataclass(frozen=True)
class RagUploadResult:
    product_id: str
    file_path: str
    operation_name: str | None
    done: bool | None
    error: dict[str, Any] | None = None


@dataclass(frozen=True)
class RagRankedProduct:
    product_id: str
    rank: int
    product_name: str = ""
    reason: str = ""


@dataclass(frozen=True)
class RagQueryResult:
    query_id: str
    query: str
    raw_text: str
    ranked_products: list[RagRankedProduct]

    def to_dict(self) -> dict[str, Any]:
        return {
            "query_id": self.query_id,
            "query": self.query,
            "raw_text": self.raw_text,
            "ranked_products": [
                {
                    "rank": product.rank,
                    "product_id": product.product_id,
                    "product_name": product.product_name,
                    "reason": product.reason,
                }
                for product in self.ranked_products
            ],
        }


@dataclass(frozen=True)
class RagEvaluationOutput:
    report: RetrievalEvaluationReport
    raw_results: list[RagQueryResult]
    diagnostics: dict[str, Any]
    report_key: str = "rag_text"

    def to_dict(self) -> dict[str, Any]:
        return {
            self.report_key: self.report.to_dict(),
            "diagnostics": self.diagnostics,
            "raw_results": [result.to_dict() for result in self.raw_results],
        }


class FileSearchClient(Protocol):
    def create_store(self, display_name: str, embedding_model: str) -> RagStoreRef:
        ...

    def upload_document(
        self,
        store_name: str,
        document: RagProductDocument,
        wait: bool,
        poll_interval_seconds: float,
        timeout_seconds: float,
    ) -> RagUploadResult:
        ...

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
        ...


class ProductTextRagCorpusBuilder:
    def build(self, config: RagTextCorpusConfig) -> list[RagProductDocument]:
        records = load_product_records(config.catalogue_path)
        if config.limit is not None:
            records = records[: config.limit]

        config.output_dir.mkdir(parents=True, exist_ok=True)
        documents = [self._write_document(config.output_dir, record) for record in records]
        manifest_path = config.manifest_path or config.output_dir / "manifest.jsonl"
        self._write_manifest(manifest_path, config.output_dir, documents)
        return documents

    def _write_document(self, output_dir: Path, record: dict[str, Any]) -> RagProductDocument:
        product_id = str(record["product_id"])
        name = str(record.get("name") or product_id)
        metadata = {
            "product_id": product_id,
            "name": name,
            "brand_or_distillery": str(record.get("brand_or_distillery") or ""),
            "style": str(record.get("style") or ""),
            "country": str(record.get("country") or ""),
            "region": str(record.get("region") or ""),
        }
        text = format_rag_product_text(record)
        path = output_dir / f"{_safe_filename(product_id)}.txt"
        path.write_text(text, encoding="utf-8")
        return RagProductDocument(
            product_id=product_id,
            name=name,
            path=path,
            metadata=metadata,
            char_count=len(text),
            mime_type="text/plain",
            byte_count=path.stat().st_size,
        )

    def _write_manifest(
        self,
        manifest_path: Path,
        root: Path,
        documents: list[RagProductDocument],
    ) -> None:
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        with manifest_path.open("w", encoding="utf-8") as handle:
            for document in documents:
                handle.write(
                    json.dumps(document.to_manifest_record(root), sort_keys=True) + "\n"
                )


class ProductMultimodalRagCorpusBuilder:
    def build(self, config: RagMultimodalCorpusConfig) -> list[RagProductDocument]:
        records = load_product_records(config.catalogue_path)
        if config.limit is not None:
            records = records[: config.limit]

        config.output_dir.mkdir(parents=True, exist_ok=True)
        documents = [self._write_document(config.output_dir, record) for record in records]
        manifest_path = config.manifest_path or config.output_dir / "manifest.jsonl"
        ProductTextRagCorpusBuilder()._write_manifest(manifest_path, config.output_dir, documents)
        return documents

    def _write_document(self, output_dir: Path, record: dict[str, Any]) -> RagProductDocument:
        product_id = str(record["product_id"])
        name = str(record.get("name") or product_id)
        image_path = record.get("cropped_product_image_path") or record.get("product_image_path")
        image_path = str(image_path) if image_path else ""
        text = format_rag_product_text(record)
        path = output_dir / f"{_safe_filename(product_id)}.pdf"
        self._write_product_pdf(path, name, text, image_path)
        metadata = {
            "product_id": product_id,
            "name": name,
            "brand_or_distillery": str(record.get("brand_or_distillery") or ""),
            "style": str(record.get("style") or ""),
            "country": str(record.get("country") or ""),
            "region": str(record.get("region") or ""),
            "corpus_type": "product_multimodal",
            "has_product_image": str(bool(image_path and Path(image_path).exists())).lower(),
        }
        return RagProductDocument(
            product_id=product_id,
            name=name,
            path=path,
            metadata=metadata,
            char_count=len(text),
            mime_type="application/pdf",
            byte_count=path.stat().st_size,
        )

    def _write_product_pdf(self, path: Path, name: str, text: str, image_path: str) -> None:
        import fitz

        doc = fitz.open()
        page = doc.new_page(width=595, height=842)
        margin = 44
        title_rect = fitz.Rect(margin, 34, 551, 78)
        page.insert_textbox(
            title_rect,
            _ascii_text(name),
            fontsize=16,
            fontname="helv",
            color=(0.08, 0.08, 0.08),
        )

        body_left = margin
        body_top = 92
        image_rect = fitz.Rect(382, 92, 551, 370)
        if image_path and Path(image_path).exists():
            image_bytes = _compressed_image_bytes(image_path, max_dimension=900, jpeg_quality=72)
            page.insert_image(image_rect, stream=image_bytes, keep_proportion=True)
        else:
            page.insert_textbox(
                image_rect,
                "No product image available.",
                fontsize=10,
                fontname="helv",
                color=(0.35, 0.35, 0.35),
            )

        y = body_top
        for line in _wrap_pdf_text(text, width=72):
            if y > 790:
                page = doc.new_page(width=595, height=842)
                y = 44
            page.insert_text(
                fitz.Point(body_left, y),
                line,
                fontsize=8.5,
                fontname="helv",
                color=(0.1, 0.1, 0.1),
            )
            y += 11

        path.parent.mkdir(parents=True, exist_ok=True)
        doc.save(path, garbage=4, deflate=True)
        doc.close()


class ProductImageRagCorpusBuilder:
    def build(self, config: RagImageCorpusConfig) -> list[RagProductDocument]:
        records = load_product_records(config.catalogue_path)
        if config.limit is not None:
            records = records[: config.limit]

        config.output_dir.mkdir(parents=True, exist_ok=True)
        documents = [self._write_document(config.output_dir, record) for record in records]
        manifest_path = config.manifest_path or config.output_dir / "manifest.jsonl"
        ProductTextRagCorpusBuilder()._write_manifest(manifest_path, config.output_dir, documents)
        return documents

    def _write_document(self, output_dir: Path, record: dict[str, Any]) -> RagProductDocument:
        product_id = str(record["product_id"])
        name = str(record.get("name") or product_id)
        source_image_path = record.get("cropped_product_image_path") or record.get("product_image_path")
        if not source_image_path:
            raise FileNotFoundError(f"{product_id} has no product image path")

        source_path = _resolve_existing_path(str(source_image_path))
        path = output_dir / f"{_safe_filename(product_id)}.jpg"
        self._write_product_image(source_path, path)
        metadata = {
            "product_id": product_id,
            "name": name,
            "brand_or_distillery": str(record.get("brand_or_distillery") or ""),
            "style": str(record.get("style") or ""),
            "country": str(record.get("country") or ""),
            "region": str(record.get("region") or ""),
            "corpus_type": "product_image",
        }
        return RagProductDocument(
            product_id=product_id,
            name=name,
            path=path,
            metadata=metadata,
            char_count=0,
            mime_type="image/jpeg",
            byte_count=path.stat().st_size,
        )

    def _write_product_image(self, source_path: Path, output_path: Path) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(
            _compressed_image_bytes(
                source_path.as_posix(),
                max_dimension=1200,
                jpeg_quality=82,
            )
        )


class RagTextStoreIngestionPipeline:
    def __init__(self, client: FileSearchClient | None = None) -> None:
        self.client = client or GeminiFileSearchClient()

    def run(self, config: RagTextStoreConfig) -> dict[str, Any]:
        documents = load_rag_documents(config.corpus_manifest_path)
        if config.limit is not None:
            documents = documents[: config.limit]

        existing_manifest = (
            _load_store_manifest(config.output_path)
            if config.resume and config.output_path.exists()
            else {}
        )
        if existing_manifest and not config.store_name:
            store = RagStoreRef(
                name=str(existing_manifest["store_name"]),
                display_name=str(existing_manifest.get("display_name") or config.display_name),
                embedding_model=str(existing_manifest.get("embedding_model") or config.embedding_model),
            )
        elif config.store_name:
            store = RagStoreRef(
                name=config.store_name,
                display_name=config.display_name,
                embedding_model=config.embedding_model,
            )
        else:
            store = self.client.create_store(config.display_name, config.embedding_model)

        upload_records = {
            str(record["product_id"]): record
            for record in existing_manifest.get("uploads", [])
            if record.get("product_id")
        }
        manifest = _build_store_manifest(
            store=store,
            config=config,
            documents=documents,
            upload_records=upload_records,
        )
        _write_store_manifest(config.output_path, manifest)

        pending_documents = [
            document
            for document in documents
            if not _is_completed_upload_record(upload_records.get(document.product_id))
        ]
        if pending_documents:
            print(
                f"Uploading {len(pending_documents)} documents to {store.name} "
                f"(concurrency={config.concurrency})"
            )

        def record_upload(upload: RagUploadResult) -> None:
            upload_records[upload.product_id] = _upload_to_manifest_record(upload)
            manifest = _build_store_manifest(
                store=store,
                config=config,
                documents=documents,
                upload_records=upload_records,
            )
            _write_store_manifest(config.output_path, manifest)

        self._upload_documents(store.name, pending_documents, config, on_upload=record_upload)

        failed_uploads = [
            record for record in upload_records.values() if record.get("error")
        ]
        if failed_uploads:
            raise RuntimeError(f"{len(failed_uploads)} File Search uploads failed; see {config.output_path}")

        return _build_store_manifest(
            store=store,
            config=config,
            documents=documents,
            upload_records=upload_records,
        )

    def _upload_documents(
        self,
        store_name: str,
        documents: list[RagProductDocument],
        config: RagTextStoreConfig,
        on_upload: Any | None = None,
    ) -> list[RagUploadResult]:
        if not documents:
            return []
        if config.concurrency <= 1:
            uploads = []
            for index, document in enumerate(documents, start=1):
                upload = self._upload_one(store_name, document, config)
                uploads.append(upload)
                if on_upload:
                    on_upload(upload)
                if _should_report_progress(index, len(documents), config.progress_every):
                    print(f"uploaded {index}/{len(documents)} documents")
                if config.sleep_seconds > 0:
                    time.sleep(config.sleep_seconds)
            return uploads

        uploads: list[RagUploadResult] = []
        with ThreadPoolExecutor(max_workers=config.concurrency) as executor:
            future_to_document = {}
            for document in documents:
                future = executor.submit(self._upload_one, store_name, document, config)
                future_to_document[future] = document
                if config.sleep_seconds > 0:
                    time.sleep(config.sleep_seconds)

            for index, future in enumerate(as_completed(future_to_document), start=1):
                document = future_to_document[future]
                try:
                    uploads.append(future.result())
                except Exception as exc:  # pragma: no cover - exercised through fake clients
                    uploads.append(
                        RagUploadResult(
                            product_id=document.product_id,
                            file_path=document.path.as_posix(),
                            operation_name=None,
                            done=False,
                            error={"type": type(exc).__name__, "message": str(exc)},
                        )
                    )
                if on_upload:
                    on_upload(uploads[-1])
                if _should_report_progress(index, len(documents), config.progress_every):
                    print(f"uploaded {index}/{len(documents)} documents")
        return uploads

    def _upload_one(
        self,
        store_name: str,
        document: RagProductDocument,
        config: RagTextStoreConfig,
    ) -> RagUploadResult:
        return self.client.upload_document(
            store_name=store_name,
            document=document,
            wait=config.wait,
            poll_interval_seconds=config.poll_interval_seconds,
            timeout_seconds=config.timeout_seconds,
        )


class RagTextEvaluationPipeline:
    def __init__(self, client: FileSearchClient | None = None) -> None:
        self.client = client or GeminiFileSearchClient()

    def run(self, config: RagTextEvaluationConfig) -> RagEvaluationOutput:
        queries = EvalQueryLoader(base_dir=config.query_base_dir).load(config.query_path)
        if config.limit is not None:
            queries = queries[: config.limit]
        product_metadata = _product_metadata_by_id(load_product_records(config.catalogue_path))
        raw_by_query_id = (
            _load_existing_rag_query_results(config.output_path)
            if config.resume and config.output_path.exists()
            else {}
        )

        for query in queries:
            if query.query_id in raw_by_query_id:
                continue
            result = self._search_with_retries(
                config=config,
                store_name=config.store_name,
                query_id=query.query_id,
                query=_rag_query_text(query.query_type, query.query),
                query_type=query.query_type,
                image_path=query.query_image_path,
            )
            raw_by_query_id[query.query_id] = result
            output = self._build_output(config, queries, raw_by_query_id, product_metadata)
            self._write_output(config.output_path, output)
            if config.sleep_seconds > 0:
                time.sleep(config.sleep_seconds)

        output = self._build_output(config, queries, raw_by_query_id, product_metadata)
        self._write_output(config.output_path, output)
        return output

    def _search_with_retries(
        self,
        config: RagTextEvaluationConfig,
        store_name: str,
        query_id: str,
        query: str,
        query_type: str,
        image_path: str | None,
    ) -> RagQueryResult:
        last_error: Exception | None = None
        for attempt in range(config.max_retries + 1):
            try:
                return self.client.search_products(
                    store_name=store_name,
                    query_id=query_id,
                    query=query,
                    query_type=query_type,
                    image_path=image_path,
                    top_k=config.top_k,
                    model_name=config.model_name,
                )
            except Exception as exc:
                last_error = exc
                if attempt >= config.max_retries:
                    break
                time.sleep(config.retry_sleep_seconds)
        assert last_error is not None
        if config.continue_on_error:
            return RagQueryResult(
                query_id=query_id,
                query=query,
                raw_text=json.dumps(
                    {
                        "error": {
                            "type": type(last_error).__name__,
                            "message": str(last_error),
                        }
                    }
                ),
                ranked_products=[],
            )
        raise last_error

    def _build_output(
        self,
        config: RagTextEvaluationConfig,
        queries: list[Any],
        raw_by_query_id: dict[str, RagQueryResult],
        product_metadata: dict[str, dict[str, Any]],
    ) -> RagEvaluationOutput:
        completed_queries = [query for query in queries if query.query_id in raw_by_query_id]
        raw_results = [raw_by_query_id[query.query_id] for query in completed_queries]
        rankings = {
            query.query_id: [
                RankedResult(
                    query_id=query.query_id,
                    product_id=product.product_id,
                    rank=product.rank,
                    score=1.0 / product.rank,
                    product_metadata=product_metadata.get(
                        product.product_id,
                        {"product_id": product.product_id, "invalid_product_id": True},
                    ),
                )
                for product in raw_by_query_id[query.query_id].ranked_products
            ]
            for query in completed_queries
        }
        report = RetrievalEvaluator(k_values=(1, 5, config.top_k)).evaluate(
            completed_queries,
            rankings,
        )
        diagnostics = build_rag_diagnostics(raw_results, product_metadata)
        return RagEvaluationOutput(
            report=report,
            raw_results=raw_results,
            diagnostics=diagnostics,
            report_key=config.report_key,
        )

    def _write_output(self, path: Path, output: RagEvaluationOutput) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(output.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")


class GeminiFileSearchClient:
    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key.strip() if api_key is not None else load_api_key()
        if not self.api_key:
            raise RuntimeError("Google API key must not be empty")
        self.client = genai.Client(api_key=self.api_key)

    def create_store(self, display_name: str, embedding_model: str) -> RagStoreRef:
        # google-genai 1.74 exposes File Search but does not yet map the documented
        # embedding_model field. Use the public REST endpoint for store creation so
        # the store is explicitly indexed with gemini-embedding-2.
        response = self._post_json(
            "https://generativelanguage.googleapis.com/v1beta/fileSearchStores",
            {"display_name": display_name, "embedding_model": embedding_model},
        )
        name = str(response["name"])
        return RagStoreRef(name=name, display_name=display_name, embedding_model=embedding_model)

    def upload_document(
        self,
        store_name: str,
        document: RagProductDocument,
        wait: bool,
        poll_interval_seconds: float,
        timeout_seconds: float,
    ) -> RagUploadResult:
        operation = self.client.file_search_stores.upload_to_file_search_store(
            file_search_store_name=store_name,
            file=document.path,
            config=types.UploadToFileSearchStoreConfig(
                display_name=document.path.name,
                mime_type=document.mime_type,
                custom_metadata=[
                    types.CustomMetadata(key=key, string_value=value)
                    for key, value in document.metadata.items()
                    if value
                ],
            ),
        )
        if wait:
            operation = self._wait_for_operation(
                operation,
                poll_interval_seconds=poll_interval_seconds,
                timeout_seconds=timeout_seconds,
            )
        return RagUploadResult(
            product_id=document.product_id,
            file_path=document.path.as_posix(),
            operation_name=operation.name,
            done=operation.done,
            error=operation.error,
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
        has_image = query_type in {"image", "image_text"}
        prompt = build_rag_query_prompt(query=query, top_k=top_k, has_image=has_image)
        contents: str | list[Any] = prompt
        if has_image:
            if not image_path:
                raise ValueError(f"{query_id} image query requires image_path")
            path = Path(image_path)
            contents = [
                prompt,
                types.Part.from_bytes(data=path.read_bytes(), mime_type=_mime_type(path)),
            ]
        response = self.client.models.generate_content(
            model=model_name,
            contents=contents,
            config=types.GenerateContentConfig(
                temperature=0,
                tools=[
                    types.Tool(
                        file_search=types.FileSearch(
                            file_search_store_names=[store_name],
                            top_k=top_k,
                        )
                    )
                ],
            ),
        )
        raw_text = response.text or ""
        return RagQueryResult(
            query_id=query_id,
            query=query,
            raw_text=raw_text,
            ranked_products=parse_rag_ranked_products(raw_text, top_k=top_k),
        )

    def _wait_for_operation(
        self,
        operation: Any,
        poll_interval_seconds: float,
        timeout_seconds: float,
    ) -> Any:
        deadline = time.monotonic() + timeout_seconds
        while not operation.done:
            if time.monotonic() >= deadline:
                raise TimeoutError(f"File Search upload operation timed out: {operation.name}")
            time.sleep(poll_interval_seconds)
            operation = self.client.operations.get(operation)
        if operation.error:
            raise RuntimeError(f"File Search upload failed: {operation.error}")
        return operation

    def _post_json(self, url: str, payload: dict[str, Any]) -> dict[str, Any]:
        request = urllib.request.Request(
            f"{url}?key={self.api_key}",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            body = error.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"File Search store creation failed: {body}") from error


def load_rag_documents(manifest_path: Path) -> list[RagProductDocument]:
    root = manifest_path.parent
    documents: list[RagProductDocument] = []
    for raw_line in manifest_path.read_text(encoding="utf-8").splitlines():
        if not raw_line.strip():
            continue
        record = json.loads(raw_line)
        path = Path(record["path"])
        if not path.is_absolute():
            path = root / path
        documents.append(
            RagProductDocument(
                product_id=str(record["product_id"]),
                name=str(record["name"]),
                path=path,
                metadata={str(key): str(value) for key, value in record.get("metadata", {}).items()},
                char_count=int(record.get("char_count", 0)),
                mime_type=str(record.get("mime_type") or "text/plain"),
                byte_count=int(record.get("byte_count", 0)),
            )
        )
    return documents


def load_store_name(path: Path) -> str:
    record = json.loads(path.read_text(encoding="utf-8"))
    return str(record["store_name"])


def _load_existing_rag_query_results(path: Path) -> dict[str, RagQueryResult]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    results: dict[str, RagQueryResult] = {}
    for record in payload.get("raw_results", []):
        query_id = str(record["query_id"])
        results[query_id] = RagQueryResult(
            query_id=query_id,
            query=str(record.get("query") or ""),
            raw_text=str(record.get("raw_text") or ""),
            ranked_products=[
                RagRankedProduct(
                    product_id=str(product.get("product_id") or ""),
                    rank=int(product.get("rank") or index),
                    product_name=str(product.get("product_name") or ""),
                    reason=str(product.get("reason") or ""),
                )
                for index, product in enumerate(record.get("ranked_products", []), start=1)
                if product.get("product_id")
            ],
        )
    return results


def _rag_query_text(query_type: str, query: str | None) -> str:
    if query and query.strip():
        return query.strip()
    if query_type == "image":
        return "Find the catalogue whisky product that matches the attached image."
    return "Find the matching whisky catalogue products."


def format_rag_product_text(record: dict[str, Any]) -> str:
    name = record.get("name") or record["product_id"]
    fields = [
        f"title: {name}",
        f"product_id: {record['product_id']}",
        "text:",
        build_product_text(record),
    ]
    return "\n".join(field for field in fields if field)


def build_rag_text_query_prompt(query: str, top_k: int) -> str:
    return build_rag_query_prompt(query=query, top_k=top_k, has_image=False)


def build_rag_query_prompt(query: str, top_k: int, has_image: bool = False) -> str:
    image_instruction = (
        "The user also attached an image. Use the image as query evidence, but use only "
        "File Search catalogue records as the source of product IDs and product names.\n"
        if has_image
        else ""
    )
    return (
        "You are searching a whisky product catalogue using File Search.\n"
        "Use only the catalogue records returned by File Search. Do not use outside knowledge.\n"
        "Catalogue records may be text documents, product image documents, or product PDF sheets; "
        "use document names and metadata when they are the only available identifiers.\n"
        "If a document name contains a catalogue product ID with a file extension, return the "
        "product ID without the file extension.\n"
        f"{image_instruction}"
        f"Return the top {top_k} matching catalogue products for the user query.\n"
        "Return JSON only, with this exact shape:\n"
        '{"results":[{"rank":1,"product_id":"...","product_name":"...","reason":"..."}]}\n'
        f"User query: {query}"
    )


def parse_rag_ranked_products(raw_text: str, top_k: int) -> list[RagRankedProduct]:
    try:
        payload = _loads_json_payload(raw_text)
    except json.JSONDecodeError:
        return []
    if isinstance(payload, dict):
        records = payload.get("results", [])
    elif isinstance(payload, list):
        records = payload
    else:
        records = []

    ranked: list[RagRankedProduct] = []
    seen: set[str] = set()
    for index, record in enumerate(records, start=1):
        if not isinstance(record, dict):
            continue
        product_id = _normalize_rag_product_id(str(record.get("product_id") or ""))
        if not product_id or product_id in seen:
            continue
        seen.add(product_id)
        rank = int(record.get("rank") or index)
        ranked.append(
            RagRankedProduct(
                product_id=product_id,
                rank=rank,
                product_name=str(record.get("product_name") or ""),
                reason=str(record.get("reason") or ""),
            )
        )
        if len(ranked) >= top_k:
            break
    return ranked


def _normalize_rag_product_id(value: str) -> str:
    product_id = Path(value.strip()).name
    lowered = product_id.lower()
    for suffix in (".pdf", ".jpg", ".jpeg", ".png", ".webp", ".txt"):
        if lowered.endswith(suffix):
            return product_id[: -len(suffix)]
    return product_id


def build_rag_diagnostics(
    raw_results: list[RagQueryResult],
    product_metadata: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    returned_ids = [
        product.product_id
        for result in raw_results
        for product in result.ranked_products
    ]
    valid_count = sum(product_id in product_metadata for product_id in returned_ids)
    invalid_ids = sorted({product_id for product_id in returned_ids if product_id not in product_metadata})
    return {
        "returned_product_id_count": len(returned_ids),
        "valid_product_id_count": valid_count,
        "invalid_product_ids": invalid_ids,
        "valid_product_id_rate": 0.0 if not returned_ids else valid_count / len(returned_ids),
    }


def _loads_json_payload(raw_text: str) -> Any:
    text = raw_text.strip()
    if text.startswith("```"):
        lines = [line for line in text.splitlines() if not line.strip().startswith("```")]
        text = "\n".join(lines).strip()
    return json.loads(text)


def _product_metadata_by_id(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    metadata: dict[str, dict[str, Any]] = {}
    for record in records:
        product_id = str(record["product_id"])
        metadata[product_id] = {
            "product_id": product_id,
            "name": record.get("name"),
            "brand_or_distillery": record.get("brand_or_distillery"),
            "style": record.get("style"),
            "country": record.get("country"),
            "region": record.get("region"),
        }
    return metadata


def _safe_filename(value: str) -> str:
    return "".join(char if char.isalnum() or char in "-_" else "-" for char in value)


def _resolve_existing_path(path_value: str) -> Path:
    path = Path(path_value)
    if not path.is_absolute():
        path = Path.cwd() / path
    if not path.exists():
        raise FileNotFoundError(path)
    return path


def _mime_type(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if suffix == ".png":
        return "image/png"
    if suffix == ".webp":
        return "image/webp"
    raise ValueError(f"unsupported image type: {path}")


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _ascii_text(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value))
    return text.encode("ascii", "ignore").decode("ascii")


def _wrap_pdf_text(text: str, width: int) -> list[str]:
    lines: list[str] = []
    for raw_line in _ascii_text(text).splitlines():
        if not raw_line.strip():
            lines.append("")
            continue
        lines.extend(textwrap.wrap(raw_line, width=width) or [""])
    return lines


def _compressed_image_bytes(
    image_path: str,
    max_dimension: int = 900,
    jpeg_quality: int = 72,
) -> bytes:
    import fitz

    pixmap = fitz.Pixmap(image_path)
    try:
        if pixmap.alpha:
            pixmap = fitz.Pixmap(fitz.csRGB, pixmap)
        while max(pixmap.width, pixmap.height) > max_dimension:
            pixmap.shrink(1)
        return pixmap.tobytes("jpeg", jpg_quality=jpeg_quality)
    finally:
        pixmap = None


def _load_store_manifest(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _build_store_manifest(
    store: RagStoreRef,
    config: RagTextStoreConfig,
    documents: list[RagProductDocument],
    upload_records: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    return {
        "store_name": store.name,
        "display_name": store.display_name,
        "embedding_model": store.embedding_model,
        "corpus_manifest_path": config.corpus_manifest_path.as_posix(),
        "document_count": len(documents),
        "concurrency": config.concurrency,
        "uploads": [
            upload_records[document.product_id]
            for document in documents
            if document.product_id in upload_records
        ],
    }


def _write_store_manifest(path: Path, manifest: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _upload_to_manifest_record(upload: RagUploadResult) -> dict[str, Any]:
    return {
        "product_id": upload.product_id,
        "file_path": upload.file_path,
        "operation_name": upload.operation_name,
        "done": upload.done,
        "error": upload.error,
    }


def _is_completed_upload_record(record: dict[str, Any] | None) -> bool:
    if not record:
        return False
    return bool(record.get("operation_name")) and not record.get("error")


def _should_report_progress(index: int, total: int, every: int) -> bool:
    if every <= 0:
        return False
    return index == total or index % every == 0
