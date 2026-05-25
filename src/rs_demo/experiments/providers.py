from __future__ import annotations

import hashlib
import inspect
import os
from pathlib import Path
from typing import Any, Protocol

import numpy as np
from google.genai import types

from rs_demo.experiments.domain import EmbeddingInput, ModalityPart
from rs_demo.gemini_embeddings import GeminiEmbeddingModel


class EmbeddingProvider(Protocol):
    model_id: str
    dimension: int
    normalization: str

    def encode_batch(self, inputs: list[EmbeddingInput]) -> np.ndarray:
        """Encode a batch of multimodal inputs into a 2D float32 matrix."""


class MockExperimentEmbeddingProvider:
    def __init__(
        self,
        model_id: str = "mock-experiment-embedding",
        dimension: int = 32,
        seed: str = "rs-demo-experiment-mock-v1",
    ) -> None:
        if dimension <= 0:
            raise ValueError("dimension must be positive")
        self.model_id = model_id
        self.dimension = dimension
        self.normalization = "l2"
        self.seed = seed

    def encode_batch(self, inputs: list[EmbeddingInput]) -> np.ndarray:
        vectors = [self._embed_one(input_item) for input_item in inputs]
        if not vectors:
            return np.empty((0, self.dimension), dtype=np.float32)
        return np.vstack(vectors)

    def _embed_one(self, input_item: EmbeddingInput) -> np.ndarray:
        payload = {
            "id": input_item.id,
            "instruction": input_item.instruction,
            "parts": [_part_fingerprint(part) for part in input_item.modality_parts],
        }
        return _hash_to_unit_vector(self.seed, repr(payload), self.dimension)


class GeminiEmbedding2Provider:
    def __init__(
        self,
        api_key: str | None = None,
        model_name: str = "gemini-embedding-2",
        dimension: int = 768,
    ) -> None:
        self.model_id = model_name
        self.dimension = dimension
        self.normalization = "provider_default"
        self.model = GeminiEmbeddingModel(api_key=api_key, model_name=model_name, dimension=dimension)

    def encode_batch(self, inputs: list[EmbeddingInput]) -> np.ndarray:
        vectors = [self._encode_one(input_item) for input_item in inputs]
        if not vectors:
            return np.empty((0, self.dimension), dtype=np.float32)
        return np.vstack(vectors)

    def _encode_one(self, input_item: EmbeddingInput) -> np.ndarray:
        contents: list[Any] = []
        if input_item.instruction:
            contents.append(input_item.instruction)
        for part in input_item.modality_parts:
            if part.kind == "text":
                contents.append(part.value)
            elif part.kind in {"image", "document"}:
                path = Path(part.value)
                contents.append(
                    types.Part.from_bytes(
                        data=path.read_bytes(),
                        mime_type=part.mime_type or _mime_type(path),
                    )
                )
            else:
                raise ValueError(f"Gemini provider does not support {part.kind!r} parts yet")
        if not contents:
            raise ValueError(f"{input_item.id} has no contents to embed")
        payload: str | list[Any] = contents[0] if len(contents) == 1 else contents
        return self.model._embed(payload)


class Qwen3VLEmbeddingProvider:
    """Optional local Qwen3-VL-Embedding provider.

    This class keeps heavyweight dependencies out of the default environment. It supports either the
    official repository import path or a SentenceTransformers fallback when those dependencies are
    installed by the user.
    """

    def __init__(
        self,
        model_name: str = "Qwen/Qwen3-VL-Embedding-8B",
        dimension: int = 4096,
        runtime: str = "official",
        normalize: bool = True,
        batch_size: int = 8,
        encode_kwargs: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        self.model_id = model_name
        self.dimension = dimension
        self.normalization = "l2" if normalize else "none"
        self.runtime = runtime
        self.normalize = normalize
        self.batch_size = batch_size
        self.encode_kwargs = encode_kwargs or {}
        self.kwargs = kwargs
        self._model: Any | None = None

    def encode_batch(self, inputs: list[EmbeddingInput]) -> np.ndarray:
        if self.runtime == "sentence-transformers":
            return self._encode_with_sentence_transformers(inputs)
        return self._encode_with_official_runtime(inputs)

    def _encode_with_sentence_transformers(self, inputs: list[EmbeddingInput]) -> np.ndarray:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise RuntimeError(
                "Qwen3VLEmbeddingProvider(runtime='sentence-transformers') requires "
                "sentence-transformers and Qwen-compatible transformers dependencies."
            ) from exc

        if self._model is None:
            self._model = SentenceTransformer(self.model_id, **self.kwargs)
        payloads = [_qwen_sentence_transformers_payload(input_item) for input_item in inputs]
        return self._encode_grouped_by_instruction(payloads, inputs)

    def _encode_with_official_runtime(self, inputs: list[EmbeddingInput]) -> np.ndarray:
        try:
            from scripts.qwen3_vl_embedding import Qwen3VLEmbedder
        except ImportError:
            try:
                from src.models.qwen3_vl_embedding import Qwen3VLEmbedder
            except ImportError as exc:
                raise RuntimeError(
                    "Qwen3VLEmbeddingProvider(runtime='official') requires the official "
                    "Qwen3-VL-Embedding repository on PYTHONPATH plus its optional dependencies."
                ) from exc

        if self._model is None:
            self._model = Qwen3VLEmbedder(model_name_or_path=self.model_id, **self.kwargs)
        payloads = [_qwen_official_payload(input_item) for input_item in inputs]
        return self._process_official_payloads(payloads)

    def _encode_grouped_by_instruction(
        self,
        payloads: list[Any],
        inputs: list[EmbeddingInput],
    ) -> np.ndarray:
        if not inputs:
            return np.empty((0, self.dimension), dtype=np.float32)
        vectors = np.empty((len(inputs), self.dimension), dtype=np.float32)
        for instruction, indices in _indices_by_instruction(inputs).items():
            batch_payloads = [payloads[index] for index in indices]
            encode_kwargs = {
                "normalize_embeddings": self.normalize,
                "batch_size": self.batch_size,
                **self.encode_kwargs,
            }
            if instruction:
                encode_kwargs["prompt"] = instruction
            batch_vectors = self._model.encode(batch_payloads, **encode_kwargs)
            batch_vectors = _validate_provider_vectors(
                batch_vectors,
                self.dimension,
                self.model_id,
            )
            if self.normalize:
                batch_vectors = _normalize_rows(batch_vectors)
            vectors[indices] = batch_vectors
        return vectors

    def _process_official_payloads(
        self,
        payloads: list[dict[str, Any]],
    ) -> np.ndarray:
        if not payloads:
            return np.empty((0, self.dimension), dtype=np.float32)
        process_signature = inspect.signature(self._model.process)
        accepts_normalize = "normalize" in process_signature.parameters

        process_kwargs: dict[str, Any] = {}
        if accepts_normalize:
            process_kwargs["normalize"] = self.normalize
        vectors = self._model.process(payloads, **process_kwargs)
        vectors = _validate_provider_vectors(vectors, self.dimension, self.model_id)
        if self.normalize and not accepts_normalize:
            vectors = _normalize_rows(vectors)
        return vectors


class QwenVllmEmbeddingProvider:
    """Qwen3-VL-Embedding provider backed by vLLM's pooling runner.

    vLLM and the model weights are imported lazily so normal unit tests and mock runs do not need
    GPU dependencies. The input formatting follows the official Qwen vLLM embedding example.
    """

    def __init__(
        self,
        model_name: str = "Qwen/Qwen3-VL-Embedding-2B",
        dimension: int = 2048,
        dtype: str = "bfloat16",
        tensor_parallel_size: int = 1,
        gpu_memory_utilization: float | None = None,
        trust_remote_code: bool = True,
        normalize: bool = True,
        default_instruction: str = "Represent the user's input.",
        **engine_kwargs: Any,
    ) -> None:
        self.model_id = model_name
        self.dimension = dimension
        self.normalization = "l2" if normalize else "provider_default"
        self.dtype = dtype
        self.tensor_parallel_size = tensor_parallel_size
        self.gpu_memory_utilization = gpu_memory_utilization
        self.trust_remote_code = trust_remote_code
        self.normalize = normalize
        self.default_instruction = default_instruction
        self.engine_kwargs = engine_kwargs
        self._llm: Any | None = None

    def encode_batch(self, inputs: list[EmbeddingInput]) -> np.ndarray:
        if not inputs:
            return np.empty((0, self.dimension), dtype=np.float32)
        llm = self._load_llm()
        payloads = [
            _prepare_qwen_vllm_input(input_item, llm, self.default_instruction)
            for input_item in inputs
        ]
        outputs = llm.embed(payloads)
        vectors = np.asarray([_vllm_embedding(output) for output in outputs], dtype=np.float32)
        vectors = _validate_provider_vectors(vectors, self.dimension, self.model_id)
        return _normalize_rows(vectors) if self.normalize else vectors

    def _load_llm(self) -> Any:
        if self._llm is not None:
            return self._llm
        try:
            from vllm import LLM
        except ImportError as exc:
            raise RuntimeError(
                "QwenVllmEmbeddingProvider requires vLLM. Install it with "
                "pip install -e '.[qwen-vllm]'."
            ) from exc

        args: dict[str, Any] = {
            "model": self.model_id,
            "runner": "pooling",
            "dtype": self.dtype,
            "tensor_parallel_size": self.tensor_parallel_size,
            "trust_remote_code": self.trust_remote_code,
        }
        if self.gpu_memory_utilization is not None:
            args["gpu_memory_utilization"] = self.gpu_memory_utilization
        args.update(self.engine_kwargs)
        self._llm = LLM(**args)
        return self._llm


class VLM2VecV2Provider:
    """Optional adapter boundary for a cloned VLM2Vec/VLM2Vec-V2 checkout."""

    def __init__(
        self,
        model_id: str = "TIGER-Lab/VLM2Vec-V2",
        dimension: int = 4096,
        repo_path: Path | str = Path("external/repos/VLM2Vec"),
    ) -> None:
        self.model_id = model_id
        self.dimension = dimension
        self.normalization = "provider_default"
        self.repo_path = Path(repo_path)

    def encode_batch(self, inputs: list[EmbeddingInput]) -> np.ndarray:
        raise RuntimeError(
            "VLM2VecV2Provider is an optional integration boundary. Clone VLM2Vec under "
            f"{self.repo_path} and add a runtime-specific wrapper before running this provider."
        )


def build_provider(name: str, options: dict[str, Any]) -> EmbeddingProvider:
    if name == "mock":
        return MockExperimentEmbeddingProvider(**options)
    if name == "gemini_embedding_2":
        return GeminiEmbedding2Provider(**options)
    if name == "qwen3_vl_embedding":
        if options.get("runtime") == "vllm":
            vllm_options = dict(options)
            vllm_options.pop("runtime")
            return QwenVllmEmbeddingProvider(**vllm_options)
        return Qwen3VLEmbeddingProvider(**options)
    if name == "qwen3_vl_embedding_vllm":
        return QwenVllmEmbeddingProvider(**options)
    if name == "vlm2vec_v2":
        return VLM2VecV2Provider(**options)
    raise ValueError(f"unknown embedding provider: {name}")


def _part_fingerprint(part: ModalityPart) -> dict[str, Any]:
    value = part.value
    if part.kind != "text":
        path = Path(value)
        if path.exists() and path.is_file():
            value = hashlib.sha256(path.read_bytes()).hexdigest()
    return {"kind": part.kind, "value": value, "mime_type": part.mime_type}


def _hash_to_unit_vector(seed: str, value: str, dimension: int) -> np.ndarray:
    values: list[float] = []
    counter = 0
    while len(values) < dimension:
        digest = hashlib.sha256(f"{seed}:{counter}:{value}".encode("utf-8")).digest()
        values.extend((byte / 127.5) - 1.0 for byte in digest)
        counter += 1
    vector = np.array(values[:dimension], dtype=np.float32)
    norm = np.linalg.norm(vector)
    return vector if norm == 0 else vector / norm


def _validate_provider_vectors(vectors: Any, dimension: int, model_id: str) -> np.ndarray:
    array = np.asarray(vectors, dtype=np.float32)
    if array.ndim != 2 or array.shape[1] != dimension:
        raise ValueError(f"{model_id} returned shape {array.shape}; expected (*, {dimension})")
    return array


def _qwen_sentence_transformers_payload(input_item: EmbeddingInput) -> Any:
    text_parts = [part.value for part in input_item.modality_parts if part.kind == "text"]
    unsupported_documents = [
        part.value
        for part in input_item.modality_parts
        if part.kind == "document" and not _qwen_document_as_image(part.value)
    ]
    if unsupported_documents:
        raise ValueError(
            "Qwen3-VL-Embedding provider can treat image-like documents as images, but "
            f"does not support these document files yet: {unsupported_documents}"
        )
    image_parts = [
        part.value
        for part in input_item.modality_parts
        if part.kind == "image" or (part.kind == "document" and _qwen_document_as_image(part.value))
    ]
    video_parts = [part.value for part in input_item.modality_parts if part.kind == "video"]
    if len(input_item.modality_parts) == 1 and text_parts:
        return text_parts[0]
    payload: dict[str, Any] = {}
    if text_parts:
        payload["text"] = "\n".join(text_parts)
    if image_parts:
        payload["image"] = image_parts[0] if len(image_parts) == 1 else image_parts
    if video_parts:
        payload["video"] = video_parts[0] if len(video_parts) == 1 else video_parts
    if not payload:
        raise ValueError(f"{input_item.id} has no Qwen-compatible text, image, or video parts")
    return payload


def _qwen_official_payload(input_item: EmbeddingInput) -> dict[str, Any]:
    payload = _qwen_sentence_transformers_payload(input_item)
    if isinstance(payload, str):
        payload = {"text": payload}
    if input_item.instruction:
        payload["instruction"] = input_item.instruction
    return payload


def _qwen_document_as_image(value: str) -> bool:
    suffix = Path(value).suffix.lower()
    return suffix in {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif"}


def _prepare_qwen_vllm_input(
    input_item: EmbeddingInput,
    llm: Any,
    default_instruction: str,
) -> dict[str, Any]:
    conversation, images = _qwen_vllm_conversation(input_item, default_instruction)
    prompt = llm.llm_engine.tokenizer.apply_chat_template(
        conversation,
        tokenize=False,
        add_generation_prompt=True,
    )
    payload: dict[str, Any] = {"prompt": prompt}
    loaded_images = [_load_qwen_vllm_image(image) for image in images]
    if loaded_images:
        payload["multi_modal_data"] = {
            "image": loaded_images[0] if len(loaded_images) == 1 else loaded_images
        }
    return payload


def _qwen_vllm_conversation(
    input_item: EmbeddingInput,
    default_instruction: str,
) -> tuple[list[dict[str, Any]], list[str]]:
    text_parts: list[str] = []
    image_parts: list[str] = []
    for part in input_item.modality_parts:
        if part.kind == "text":
            text_parts.append(part.value)
        elif part.kind == "image":
            image_parts.append(part.value)
        else:
            raise ValueError(
                "Qwen vLLM provider currently supports text and image parts. "
                f"{input_item.id} contains unsupported {part.kind!r} part."
            )

    content: list[dict[str, Any]] = []
    for image in image_parts:
        content.append({"type": "image", "image": _qwen_vllm_image_uri(image)})
    text = "\n".join(text_parts)
    content.append({"type": "text", "text": text})

    instruction = input_item.instruction or default_instruction
    conversation = [
        {"role": "system", "content": [{"type": "text", "text": instruction}]},
        {"role": "user", "content": content},
    ]
    return conversation, image_parts


def _qwen_vllm_image_uri(value: str) -> str:
    if value.startswith(("http://", "https://", "oss://", "file://")):
        return value
    return "file://" + os.path.abspath(value)


def _load_qwen_vllm_image(value: str) -> Any:
    if value.startswith(("http://", "https://", "oss://")):
        try:
            from vllm.multimodal.utils import fetch_image
        except ImportError as exc:
            raise RuntimeError("vLLM image URL loading requires vllm.multimodal.utils.fetch_image.") from exc
        return fetch_image(value)

    path = Path(value.removeprefix("file://"))
    if not path.exists():
        raise FileNotFoundError(f"Qwen vLLM image file does not exist: {path}")
    try:
        from PIL import Image
    except ImportError as exc:
        raise RuntimeError("Qwen vLLM image loading requires Pillow, usually installed with vLLM.") from exc
    return Image.open(path).convert("RGB")


def _vllm_embedding(output: Any) -> Any:
    try:
        return output.outputs.embedding
    except AttributeError as exc:
        raise ValueError(f"Unexpected vLLM embedding output shape: {output!r}") from exc


def _normalize_rows(vectors: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    return np.divide(
        vectors,
        norms,
        out=np.zeros_like(vectors, dtype=np.float32),
        where=norms != 0,
    )


def _indices_by_instruction(inputs: list[EmbeddingInput]) -> dict[str | None, list[int]]:
    groups: dict[str | None, list[int]] = {}
    for index, input_item in enumerate(inputs):
        groups.setdefault(input_item.instruction, []).append(index)
    return groups


def _mime_type(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if suffix == ".png":
        return "image/png"
    if suffix == ".webp":
        return "image/webp"
    if suffix == ".pdf":
        return "application/pdf"
    raise ValueError(f"unsupported file type: {path}")
