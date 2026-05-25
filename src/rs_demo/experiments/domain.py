from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal


Modality = Literal["text", "image", "video", "audio", "document"]


@dataclass(frozen=True)
class ModalityPart:
    kind: Modality
    value: str
    mime_type: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        record: dict[str, Any] = {"kind": self.kind, "value": self.value}
        if self.mime_type:
            record["mime_type"] = self.mime_type
        if self.metadata:
            record["metadata"] = self.metadata
        return record

    @classmethod
    def from_dict(cls, record: dict[str, Any]) -> ModalityPart:
        return cls(
            kind=record["kind"],
            value=str(record["value"]),
            mime_type=record.get("mime_type"),
            metadata=dict(record.get("metadata") or {}),
        )


@dataclass(frozen=True)
class EmbeddingInput:
    id: str
    modality_parts: list[ModalityPart]
    instruction: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        record: dict[str, Any] = {
            "id": self.id,
            "modality_parts": [part.to_dict() for part in self.modality_parts],
            "metadata": self.metadata,
        }
        if self.instruction:
            record["instruction"] = self.instruction
        return record

    @classmethod
    def from_dict(cls, record: dict[str, Any]) -> EmbeddingInput:
        return cls(
            id=str(record["id"]),
            modality_parts=[ModalityPart.from_dict(part) for part in record["modality_parts"]],
            instruction=record.get("instruction"),
            metadata=dict(record.get("metadata") or {}),
        )


@dataclass(frozen=True)
class RetrievalItem:
    id: str
    modality_parts: list[ModalityPart]
    instruction: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def as_embedding_input(self, view: str) -> EmbeddingInput:
        parts = select_parts_for_view(self.modality_parts, view)
        if not parts:
            raise ValueError(f"{self.id} has no modality parts for view {view!r}")
        return EmbeddingInput(
            id=self.id,
            modality_parts=parts,
            instruction=self.instruction,
            metadata=self.metadata | {"view": view},
        )


@dataclass(frozen=True)
class TaskSpec:
    task_id: str
    category: str
    query_view: str
    corpus_view: str
    query_ids: list[str]
    corpus_ids: list[str] | None = None
    metrics: tuple[int, ...] = (1, 5, 10)
    similarity: Literal["cosine", "dot"] = "cosine"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RetrievalDataset:
    dataset_id: str
    corpus: list[RetrievalItem]
    queries: list[RetrievalItem]
    qrels: dict[str, list[str]]
    task_specs: list[TaskSpec]
    candidate_ids: dict[str, list[str]] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def corpus_by_id(self) -> dict[str, RetrievalItem]:
        return {item.id: item for item in self.corpus}

    @property
    def queries_by_id(self) -> dict[str, RetrievalItem]:
        return {item.id: item for item in self.queries}

    def validate(self) -> None:
        corpus_ids = {item.id for item in self.corpus}
        query_ids = {item.id for item in self.queries}
        if len(corpus_ids) != len(self.corpus):
            raise ValueError(f"{self.dataset_id} has duplicate corpus item IDs")
        if len(query_ids) != len(self.queries):
            raise ValueError(f"{self.dataset_id} has duplicate query item IDs")

        for query_id, relevant_ids in self.qrels.items():
            if query_id not in query_ids:
                raise ValueError(f"qrels reference unknown query_id: {query_id}")
            missing = [corpus_id for corpus_id in relevant_ids if corpus_id not in corpus_ids]
            if missing:
                raise ValueError(f"qrels for {query_id} reference unknown corpus IDs: {missing}")

        for query_id, candidates in self.candidate_ids.items():
            if query_id not in query_ids:
                raise ValueError(f"candidate_ids reference unknown query_id: {query_id}")
            missing = [corpus_id for corpus_id in candidates if corpus_id not in corpus_ids]
            if missing:
                raise ValueError(f"candidate_ids for {query_id} reference unknown corpus IDs: {missing}")
            candidate_relevant_ids = self.qrels.get(query_id)
            if candidate_relevant_ids and not set(candidate_relevant_ids).intersection(candidates):
                raise ValueError(f"candidate_ids for {query_id} do not include any relevant qrels")

        for task in self.task_specs:
            missing_queries = [query_id for query_id in task.query_ids if query_id not in query_ids]
            if missing_queries:
                raise ValueError(f"{task.task_id} references unknown query IDs: {missing_queries}")
            if task.corpus_ids is not None:
                missing_corpus = [
                    corpus_id for corpus_id in task.corpus_ids if corpus_id not in corpus_ids
                ]
                if missing_corpus:
                    raise ValueError(f"{task.task_id} references unknown corpus IDs: {missing_corpus}")
            missing_qrels = [query_id for query_id in task.query_ids if query_id not in self.qrels]
            if missing_qrels:
                raise ValueError(f"{task.task_id} has queries without qrels: {missing_qrels}")


def select_parts_for_view(parts: list[ModalityPart], view: str) -> list[ModalityPart]:
    if view in {"multimodal", "all"}:
        return list(parts)
    if view == "image_text":
        return [part for part in parts if part.kind in {"text", "image"}]
    if view == "video_text":
        return [part for part in parts if part.kind in {"text", "video"}]
    if view == "document_text":
        return [part for part in parts if part.kind in {"text", "document", "image"}]
    return [part for part in parts if part.kind == view]


def resolve_part_path(part: ModalityPart, base_dir: Path | str = ".") -> Path | None:
    if part.kind == "text":
        return None
    path = Path(part.value)
    if path.is_absolute():
        return path
    return Path(base_dir) / path
