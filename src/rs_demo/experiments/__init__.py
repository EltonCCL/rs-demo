"""Flexible multimodal embedding experiment framework."""

from rs_demo.experiments.adapters import (
    DatasetAdapter,
    MMEBV2Adapter,
    MMEBV2MetadataSmokeAdapter,
    WhiskyDatasetAdapter,
)
from rs_demo.experiments.config import ExperimentConfig, load_experiment_config
from rs_demo.experiments.downloads import (
    MMEBV2DownloadConfig,
    MMEBV2DownloadResult,
    MMEBV2Vlm2VecSetupConfig,
    MMEBV2Vlm2VecSetupResult,
    download_mmeb_v2,
    setup_mmeb_v2_vlm2vec_eval,
)
from rs_demo.experiments.domain import (
    EmbeddingInput,
    ModalityPart,
    RetrievalDataset,
    RetrievalItem,
    TaskSpec,
)
from rs_demo.experiments.metrics import RetrievalMetrics, evaluate_rankings
from rs_demo.experiments.providers import (
    EmbeddingProvider,
    GeminiEmbedding2Provider,
    MockExperimentEmbeddingProvider,
    Qwen3VLEmbeddingProvider,
    QwenVllmEmbeddingProvider,
    VLM2VecV2Provider,
)
from rs_demo.experiments.runner import ExperimentRunResult, ExperimentRunner
from rs_demo.experiments.store import GenericEmbeddingStore

__all__ = [
    "DatasetAdapter",
    "EmbeddingInput",
    "EmbeddingProvider",
    "ExperimentConfig",
    "ExperimentRunResult",
    "ExperimentRunner",
    "GeminiEmbedding2Provider",
    "GenericEmbeddingStore",
    "MMEBV2Adapter",
    "MMEBV2DownloadConfig",
    "MMEBV2DownloadResult",
    "MMEBV2MetadataSmokeAdapter",
    "MMEBV2Vlm2VecSetupConfig",
    "MMEBV2Vlm2VecSetupResult",
    "MockExperimentEmbeddingProvider",
    "ModalityPart",
    "Qwen3VLEmbeddingProvider",
    "QwenVllmEmbeddingProvider",
    "RetrievalDataset",
    "RetrievalItem",
    "RetrievalMetrics",
    "TaskSpec",
    "VLM2VecV2Provider",
    "WhiskyDatasetAdapter",
    "download_mmeb_v2",
    "evaluate_rankings",
    "load_experiment_config",
    "setup_mmeb_v2_vlm2vec_eval",
]
