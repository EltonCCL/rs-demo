from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Protocol

from rs_demo.embeddings import build_product_text, load_jsonl_records
from rs_demo.experiments.domain import ModalityPart, RetrievalDataset, RetrievalItem, TaskSpec
from rs_demo.queries import EvalQueryLoader


class DatasetAdapter(Protocol):
    adapter_id: str

    def load(self, *, limit_queries: int | None = None, limit_corpus: int | None = None) -> RetrievalDataset:
        """Load a retrieval dataset without mutating source data."""


class WhiskyDatasetAdapter:
    adapter_id = "whisky_v1"

    def __init__(
        self,
        catalogue_path: Path | str = Path("data/extracted/product_parse_sample.jsonl"),
        query_paths: dict[str, Path | str] | None = None,
        base_dir: Path | str = ".",
        dataset_id: str = "whisky",
    ) -> None:
        self.catalogue_path = Path(catalogue_path)
        self.query_paths = {
            "text": Path("data/eval/text_queries.jsonl"),
            "image": Path("data/eval/image_queries.jsonl"),
            "image_text": Path("data/eval/image_text_queries.jsonl"),
            "cropped_image_text": Path("data/eval/cropped_image_text_queries.jsonl"),
        } | {key: Path(value) for key, value in (query_paths or {}).items()}
        self.base_dir = Path(base_dir)
        self.dataset_id = dataset_id

    def load(self, *, limit_queries: int | None = None, limit_corpus: int | None = None) -> RetrievalDataset:
        product_records = load_jsonl_records(self.catalogue_path)
        if limit_corpus is not None:
            product_records = product_records[:limit_corpus]
        corpus = [_whisky_product_item(record) for record in product_records]
        corpus_ids = {item.id for item in corpus}

        all_queries: list[RetrievalItem] = []
        qrels: dict[str, list[str]] = {}
        task_specs: list[TaskSpec] = []
        for name, path in self.query_paths.items():
            if not path.exists():
                continue
            queries = EvalQueryLoader(base_dir=self.base_dir).load(path)
            if limit_queries is not None:
                queries = queries[:limit_queries]
            task_query_ids: list[str] = []
            for query in queries:
                relevant_ids = [
                    product_id
                    for product_id in query.relevant_product_ids
                    if product_id in corpus_ids
                ]
                if not relevant_ids:
                    continue
                item = _whisky_query_item(query.to_record())
                all_queries.append(item)
                qrels[item.id] = relevant_ids
                task_query_ids.append(item.id)
            if task_query_ids:
                task_specs.append(
                    TaskSpec(
                        task_id=f"whisky_{name}",
                        category=name,
                        query_view=_query_view_for_whisky_mode(name),
                        corpus_view=_corpus_view_for_whisky_mode(name),
                        query_ids=task_query_ids,
                        metrics=(1, 5, 10),
                    )
                )

        dataset = RetrievalDataset(
            dataset_id=self.dataset_id,
            corpus=corpus,
            queries=all_queries,
            qrels=qrels,
            task_specs=task_specs,
            metadata={
                "adapter_id": self.adapter_id,
                "catalogue_path": str(self.catalogue_path),
                "query_paths": {key: str(value) for key, value in self.query_paths.items()},
            },
        )
        dataset.validate()
        return dataset


class MMEBV2Adapter:
    """Bridge local MMEB-V2-style files into the generic retrieval dataset.

    The adapter deliberately leaves third-party files untouched. It accepts JSONL/JSON records with
    common retrieval fields (`query`, `positive`, `candidate`, `image`, `video`, etc.) so preserved
    MMEB-V2 task directories can be adapted incrementally as their exact local layout evolves.
    """

    adapter_id = "mmeb_v2_bridge_v1"

    def __init__(
        self,
        dataset_root: Path | str = Path("data/external/mmeb-v2"),
        dataset_id: str = "mmeb_v2",
    ) -> None:
        self.dataset_root = Path(dataset_root)
        self.dataset_id = dataset_id

    def load(self, *, limit_queries: int | None = None, limit_corpus: int | None = None) -> RetrievalDataset:
        if not self.dataset_root.exists():
            raise FileNotFoundError(f"MMEB-V2 dataset root does not exist: {self.dataset_root}")

        corpus_by_id: dict[str, RetrievalItem] = {}
        queries: list[RetrievalItem] = []
        qrels: dict[str, list[str]] = {}
        candidate_ids: dict[str, list[str]] = {}
        query_ids_by_task: dict[str, list[str]] = {}
        categories_by_task: dict[str, str] = {}

        for path in sorted(self.dataset_root.rglob("*")):
            if path.suffix.lower() not in {".jsonl", ".json"} or path.name.startswith("."):
                continue
            task_id = _task_id_for_path(self.dataset_root, path)
            category = _category_for_path(self.dataset_root, path)
            for record in _load_records(path):
                if limit_queries is not None and len(queries) >= limit_queries:
                    break
                parsed = _parse_mmeb_record(record, self.dataset_root, task_id)
                if parsed is None:
                    continue
                query_item, positive_items, negative_items = parsed
                queries.append(query_item)
                query_ids_by_task.setdefault(task_id, []).append(query_item.id)
                categories_by_task[task_id] = category
                relevant_ids: list[str] = []
                query_candidate_ids: list[str] = []
                for item in positive_items + negative_items:
                    if limit_corpus is not None and item.id not in corpus_by_id:
                        if len(corpus_by_id) >= limit_corpus:
                            continue
                    corpus_by_id.setdefault(item.id, item)
                    query_candidate_ids.append(item.id)
                for item in positive_items:
                    if item.id in corpus_by_id:
                        relevant_ids.append(item.id)
                if relevant_ids:
                    qrels[query_item.id] = relevant_ids
                    if query_candidate_ids:
                        candidate_ids[query_item.id] = _ordered_unique(query_candidate_ids)

        task_specs = [
            TaskSpec(
                task_id=task_id,
                category=categories_by_task.get(task_id, "unknown"),
                query_view="multimodal",
                corpus_view="multimodal",
                query_ids=query_ids,
                metrics=(1, 5, 10),
            )
            for task_id, query_ids in sorted(query_ids_by_task.items())
            if any(query_id in qrels for query_id in query_ids)
        ]
        if not task_specs:
            raise ValueError(_empty_mmeb_message(self.dataset_root))
        dataset = RetrievalDataset(
            dataset_id=self.dataset_id,
            corpus=list(corpus_by_id.values()),
            queries=[query for query in queries if query.id in qrels],
            qrels=qrels,
            task_specs=task_specs,
            candidate_ids=candidate_ids,
            metadata={"adapter_id": self.adapter_id, "dataset_root": str(self.dataset_root)},
        )
        dataset.validate()
        return dataset


class MMEBV2MetadataSmokeAdapter:
    """Tiny text-only smoke bridge for the MMEB-V2 metadata download profile.

    The official MMEB-V2 benchmark requires separate test records and visual assets. The metadata
    profile available in this repo is still useful for validating our experiment plumbing, so this
    adapter maps video QA metadata rows into a small answer-retrieval task without mutating the
    third-party tree. Metrics from this adapter are not benchmark-comparable.
    """

    adapter_id = "mmeb_v2_metadata_smoke_v1"

    def __init__(
        self,
        dataset_root: Path | str = Path("data/external/mmeb-v2/hf-repo"),
        metadata_path: Path | str = Path("video-tasks/data/activitynetqa.jsonl"),
        dataset_id: str = "mmeb_v2_metadata_smoke",
        task_id: str = "mmeb_v2_activitynetqa_answer_smoke",
    ) -> None:
        self.dataset_root = Path(dataset_root)
        self.metadata_path = Path(metadata_path)
        self.dataset_id = dataset_id
        self.task_id = task_id

    def load(self, *, limit_queries: int | None = None, limit_corpus: int | None = None) -> RetrievalDataset:
        path = self.metadata_path
        if not path.is_absolute():
            path = self.dataset_root / path
        if not path.exists():
            raise FileNotFoundError(f"MMEB-V2 metadata smoke file does not exist: {path}")

        records = [
            record
            for record in _load_records(path)
            if record.get("question_id") and record.get("question") and record.get("answer")
        ]
        if limit_queries is not None:
            records = records[:limit_queries]
        if not records:
            raise ValueError(f"MMEB-V2 metadata smoke file has no usable QA records: {path}")

        answers = _ordered_unique(str(record["answer"]) for record in records)
        if limit_corpus is not None:
            answers = answers[:limit_corpus]
        corpus = [
            RetrievalItem(
                id=f"{self.task_id}:answer:{_safe_record_id(answer)}",
                modality_parts=[ModalityPart(kind="text", value=answer)],
                metadata={"answer": answer, "source_path": str(path)},
            )
            for answer in answers
        ]
        corpus_by_answer = {item.metadata["answer"]: item.id for item in corpus}

        queries: list[RetrievalItem] = []
        qrels: dict[str, list[str]] = {}
        for record in records:
            answer = str(record["answer"])
            if answer not in corpus_by_answer:
                continue
            query_id = f"{self.task_id}:{record['question_id']}"
            queries.append(
                RetrievalItem(
                    id=query_id,
                    modality_parts=[ModalityPart(kind="text", value=str(record["question"]))],
                    instruction="Retrieve the answer to the video question.",
                    metadata={
                        "source_path": str(path),
                        "source_record_id": str(record["question_id"]),
                        "video_name": record.get("video_name"),
                        "answer": answer,
                        "note": "text-only metadata smoke; visual evidence is not embedded",
                    },
                )
            )
            qrels[query_id] = [corpus_by_answer[answer]]

        task = TaskSpec(
            task_id=self.task_id,
            category="video_qa_metadata_smoke",
            query_view="text",
            corpus_view="text",
            query_ids=[query.id for query in queries],
            corpus_ids=[item.id for item in corpus],
            metrics=(1, 2),
            metadata={"source_path": str(path), "benchmark_comparable": False},
        )
        dataset = RetrievalDataset(
            dataset_id=self.dataset_id,
            corpus=corpus,
            queries=queries,
            qrels=qrels,
            task_specs=[task],
            metadata={
                "adapter_id": self.adapter_id,
                "dataset_root": str(self.dataset_root),
                "metadata_path": str(path),
                "benchmark_comparable": False,
                "note": (
                    "Text-only smoke derived from MMEB-V2 metadata profile. Use the official "
                    "MMEB-V2 assets/test splits for benchmark-comparable scores."
                ),
            },
        )
        dataset.validate()
        return dataset


def build_dataset_adapter(name: str, options: dict[str, Any]) -> DatasetAdapter:
    if name == "whisky":
        return WhiskyDatasetAdapter(**options)
    if name == "mmeb_v2":
        return MMEBV2Adapter(**options)
    if name == "mmeb_v2_metadata_smoke":
        return MMEBV2MetadataSmokeAdapter(**options)
    raise ValueError(f"unknown dataset adapter: {name}")


def _whisky_product_item(record: dict[str, Any]) -> RetrievalItem:
    parts = [ModalityPart(kind="text", value=build_product_text(record))]
    image_path = record.get("cropped_product_image_path") or record.get("product_image_path")
    if image_path:
        parts.append(ModalityPart(kind="image", value=str(image_path)))
    return RetrievalItem(
        id=str(record["product_id"]),
        modality_parts=parts,
        metadata={
            "name": record.get("name"),
            "brand_or_distillery": record.get("brand_or_distillery"),
            "style": record.get("style"),
            "country": record.get("country"),
            "source_page": record.get("source_page"),
        },
    )


def _whisky_query_item(record: dict[str, Any]) -> RetrievalItem:
    parts: list[ModalityPart] = []
    if record.get("query"):
        parts.append(ModalityPart(kind="text", value=str(record["query"])))
    if record.get("query_image_path"):
        parts.append(ModalityPart(kind="image", value=str(record["query_image_path"])))
    return RetrievalItem(
        id=str(record["query_id"]),
        modality_parts=parts,
        instruction="task: search result | query",
        metadata={key: value for key, value in record.items() if key != "relevant_product_ids"},
    )


def _query_view_for_whisky_mode(name: str) -> str:
    if name == "text":
        return "text"
    if name == "image":
        return "image"
    return "image_text"


def _corpus_view_for_whisky_mode(name: str) -> str:
    if name in {"image", "cropped_image_text"}:
        return "image"
    if name == "text":
        return "text"
    return "image_text"


def _load_records(path: Path) -> list[dict[str, Any]]:
    if path.suffix.lower() == ".jsonl":
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return [record for record in payload if isinstance(record, dict)]
    if isinstance(payload, dict):
        for key in ("data", "examples", "records", "queries"):
            value = payload.get(key)
            if isinstance(value, list):
                return [record for record in value if isinstance(record, dict)]
    return []


def _parse_mmeb_record(
    record: dict[str, Any],
    dataset_root: Path,
    task_id: str,
) -> tuple[RetrievalItem, list[RetrievalItem], list[RetrievalItem]] | None:
    query_id = str(record.get("query_id") or record.get("qid") or record.get("id") or "")
    if not query_id:
        return None
    query_parts = _parts_from_record(record, dataset_root, prefixes=("query_", "qry_"))
    if not query_parts and record.get("query"):
        query_parts = [ModalityPart(kind="text", value=str(record["query"]))]
    if not query_parts:
        return None

    positives = _candidate_items(record, dataset_root, task_id, "positive")
    negatives = _candidate_items(record, dataset_root, task_id, "negative")
    if not positives:
        candidates = _candidate_items(record, dataset_root, task_id, "candidate")
        positives = candidates[:1]
        negatives = candidates[1:]
    if not positives:
        return None
    query_item = RetrievalItem(
        id=f"{task_id}:{query_id}",
        modality_parts=query_parts,
        instruction=record.get("instruction") or record.get("task_instruction"),
        metadata={"task_id": task_id, "source_record_id": query_id},
    )
    return query_item, positives, negatives


def _candidate_items(
    record: dict[str, Any],
    dataset_root: Path,
    task_id: str,
    prefix: str,
) -> list[RetrievalItem]:
    values = (
        record.get(f"{prefix}s")
        or record.get(f"{prefix}_items")
        or record.get(f"{prefix}_passages")
        or record.get(prefix)
        or record.get(f"{prefix}_text")
        or record.get(f"{prefix}_image")
    )
    if values is None:
        return []
    if not isinstance(values, list):
        values = [values]
    items: list[RetrievalItem] = []
    for index, value in enumerate(values):
        if isinstance(value, dict):
            item_id = str(
                value.get("id")
                or value.get("docid")
                or value.get("corpus_id")
                or value.get("target_id")
                or f"{prefix}-{index}"
            )
            parts = _parts_from_record(value, dataset_root, prefixes=("",))
            metadata = {key: value for key, value in value.items() if key not in _MMEB_PART_KEYS}
        else:
            item_id = f"{prefix}-{index}"
            parts = [ModalityPart(kind="text", value=str(value))]
            metadata = {}
        if parts:
            items.append(
                RetrievalItem(
                    id=f"{task_id}:candidate:{item_id}",
                    modality_parts=parts,
                    metadata={"task_id": task_id, "role": prefix} | metadata,
                )
            )
    return items


_MMEB_PART_KEYS = {
    "text",
    "query",
    "image",
    "image_path",
    "video",
    "video_path",
    "document",
    "document_path",
    "pdf",
}


def _parts_from_record(
    record: dict[str, Any],
    dataset_root: Path,
    prefixes: tuple[str, ...],
) -> list[ModalityPart]:
    parts: list[ModalityPart] = []
    for prefix in prefixes:
        text = record.get(f"{prefix}text") or record.get(f"{prefix}query")
        if text:
            parts.append(ModalityPart(kind="text", value=str(text)))
        for kind, keys in {
            "image": ("image", "image_path"),
            "video": ("video", "video_path"),
            "document": ("document", "document_path", "pdf"),
        }.items():
            for key in keys:
                value = record.get(f"{prefix}{key}")
                if value:
                    parts.append(ModalityPart(kind=kind, value=_resolve_external_path(value, dataset_root)))
                    break
    return parts


def _resolve_external_path(value: Any, dataset_root: Path) -> str:
    path = Path(str(value))
    if path.is_absolute() or str(value).startswith(("http://", "https://")):
        return str(value)
    return str(dataset_root / path)


def _ordered_unique(values: Any) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result


def _safe_record_id(value: str) -> str:
    safe = "".join(ch.lower() if ch.isalnum() else "-" for ch in value.strip())
    return "-".join(part for part in safe.split("-") if part) or "empty"


def _empty_mmeb_message(dataset_root: Path) -> str:
    manifest_path = dataset_root.parent / "download_manifest.json"
    profile = None
    if manifest_path.exists():
        try:
            profile = json.loads(manifest_path.read_text(encoding="utf-8")).get("profile")
        except json.JSONDecodeError:
            profile = None
    if profile == "metadata":
        return (
            "MMEB-V2 adapter found no retrieval tasks. The local tree was downloaded with "
            "the metadata profile, which is useful for inspecting the official layout but does "
            "not include enough assets/test qrels for an experiment run."
        )
    return (
        "MMEB-V2 adapter found no retrieval tasks. Check that the local MMEB-V2 test files "
        "contain query/candidate/qrel fields and that extracted assets remain under the "
        f"external dataset root: {dataset_root}"
    )


def _task_id_for_path(root: Path, path: Path) -> str:
    relative = path.relative_to(root).with_suffix("")
    return "/".join(relative.parts)


def _category_for_path(root: Path, path: Path) -> str:
    relative = path.relative_to(root)
    return relative.parts[0] if relative.parts else "unknown"
