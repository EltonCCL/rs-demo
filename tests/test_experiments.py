from __future__ import annotations

import json
import sys
import tarfile
import types
from pathlib import Path

import numpy as np

from rs_demo.experiments import (
    EmbeddingInput,
    ExperimentConfig,
    ExperimentRunner,
    GenericEmbeddingStore,
    MMEBV2Adapter,
    MMEBV2DownloadConfig,
    MMEBV2MetadataSmokeAdapter,
    MMEBV2Vlm2VecSetupConfig,
    MockExperimentEmbeddingProvider,
    ModalityPart,
    Qwen3VLEmbeddingProvider,
    QwenVllmEmbeddingProvider,
    RetrievalDataset,
    RetrievalItem,
    TaskSpec,
    WhiskyDatasetAdapter,
    download_mmeb_v2,
    evaluate_rankings,
    load_experiment_config,
    setup_mmeb_v2_vlm2vec_eval,
)


def test_generic_embedding_store_round_trips_vectors(tmp_path: Path) -> None:
    store = GenericEmbeddingStore(tmp_path)
    items = [
        EmbeddingInput(
            id="q1",
            modality_parts=[ModalityPart(kind="text", value="peated whisky")],
            instruction="retrieve",
        )
    ]
    vectors = np.array([[1.0, 0.0]], dtype=np.float32)

    store.write(
        tmp_path / "artifact",
        items=items,
        vectors=vectors,
        manifest={"model_id": "fake", "view": "text"},
    )
    loaded = store.read(tmp_path / "artifact")

    assert loaded.ids == ["q1"]
    np.testing.assert_allclose(loaded.vectors, vectors)
    assert loaded.manifest["dimension"] == 2


def test_evaluate_rankings_reports_recall_mrr_and_ndcg() -> None:
    report = evaluate_rankings(
        rankings={"q1": ["d2", "d1"], "q2": ["d3"]},
        qrels={"q1": ["d1", "d4"], "q2": ["d3"]},
        query_categories={"q1": "image", "q2": "image"},
        k_values=(1, 2),
    )

    assert report.metrics["hit_at_1"] == 0.5
    assert report.metrics["recall_at_2"] == 0.75
    assert report.metrics["mrr"] == 0.75
    assert report.metrics_by_category["image"]["ndcg_at_2"] > 0


def test_whisky_adapter_maps_catalogue_and_queries(tmp_path: Path) -> None:
    catalogue = tmp_path / "products.jsonl"
    queries = tmp_path / "text_queries.jsonl"
    catalogue.write_text(
        (
            '{"product_id":"p001","name":"A","description":"Apple smoke.",'
            '"brand_or_distillery":"A"}\n'
            '{"product_id":"p002","name":"B","description":"Honey.",'
            '"brand_or_distillery":"B"}\n'
        ),
        encoding="utf-8",
    )
    queries.write_text(
        (
            '{"query_id":"tq001","query_type":"text","query_style":"metadata_brand",'
            '"query":"I want A.","relevant_product_ids":["p001"]}\n'
        ),
        encoding="utf-8",
    )

    dataset = WhiskyDatasetAdapter(
        catalogue_path=catalogue,
        query_paths={"text": queries},
        dataset_id="whisky_test",
    ).load()

    assert dataset.dataset_id == "whisky_test"
    assert [item.id for item in dataset.corpus] == ["p001", "p002"]
    assert [item.id for item in dataset.queries] == ["tq001"]
    assert dataset.qrels == {"tq001": ["p001"]}
    assert dataset.task_specs[0].query_view == "text"


def test_mmeb_adapter_preserves_external_paths_and_builds_tasks(tmp_path: Path) -> None:
    root = tmp_path / "mmeb-v2"
    task_dir = root / "image" / "sample_task"
    task_dir.mkdir(parents=True)
    image_path = root / "images" / "query.jpg"
    image_path.parent.mkdir()
    image_path.write_bytes(b"fake image")
    (task_dir / "test.jsonl").write_text(
        json.dumps(
            {
                "query_id": "q1",
                "query_text": "find this bottle",
                "query_image": "images/query.jpg",
                "positives": [{"id": "d1", "text": "matching bottle"}],
                "negatives": [{"id": "d2", "text": "other bottle"}],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    dataset = MMEBV2Adapter(dataset_root=root, dataset_id="mmeb_fixture").load()

    assert dataset.dataset_id == "mmeb_fixture"
    assert dataset.task_specs[0].category == "image"
    assert dataset.queries[0].modality_parts[1].value == str(root / "images/query.jpg")
    assert dataset.qrels[dataset.queries[0].id] == ["image/sample_task/test:candidate:d1"]
    assert dataset.candidate_ids[dataset.queries[0].id] == [
        "image/sample_task/test:candidate:d1",
        "image/sample_task/test:candidate:d2",
    ]


def test_mmeb_adapter_treats_first_candidate_as_groundtruth(tmp_path: Path) -> None:
    root = tmp_path / "mmeb-v2"
    task_dir = root / "image" / "candidate_task"
    task_dir.mkdir(parents=True)
    (task_dir / "test.jsonl").write_text(
        json.dumps(
            {
                "query_id": "q1",
                "query": "select the matching caption",
                "candidates": [
                    {"id": "d1", "text": "correct target"},
                    {"id": "d2", "text": "distractor"},
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    dataset = MMEBV2Adapter(dataset_root=root, dataset_id="mmeb_fixture").load()

    assert dataset.qrels[dataset.queries[0].id] == ["image/candidate_task/test:candidate:d1"]
    assert dataset.candidate_ids[dataset.queries[0].id] == [
        "image/candidate_task/test:candidate:d1",
        "image/candidate_task/test:candidate:d2",
    ]


def test_mmeb_adapter_explains_metadata_only_profile(tmp_path: Path) -> None:
    root = tmp_path / "mmeb-v2" / "hf-repo"
    root.mkdir(parents=True)
    (root.parent / "download_manifest.json").write_text(
        json.dumps({"profile": "metadata"}),
        encoding="utf-8",
    )
    (root / "metadata.jsonl").write_text(
        json.dumps({"query_id": "q1", "query": "metadata only"}) + "\n",
        encoding="utf-8",
    )

    try:
        MMEBV2Adapter(dataset_root=root, dataset_id="mmeb_metadata").load()
    except ValueError as exc:
        assert "metadata profile" in str(exc)
    else:
        raise AssertionError("expected metadata-only MMEB tree to explain missing qrels")


def test_mmeb_metadata_smoke_adapter_builds_text_qa_task(tmp_path: Path) -> None:
    root = tmp_path / "mmeb-v2" / "hf-repo"
    data_dir = root / "video-tasks" / "data"
    data_dir.mkdir(parents=True)
    (data_dir / "activitynetqa.jsonl").write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "video_name": "v1",
                        "question_id": "q1",
                        "question": "is the person outdoors",
                        "answer": "yes",
                    }
                ),
                json.dumps(
                    {
                        "video_name": "v2",
                        "question_id": "q2",
                        "question": "is it raining",
                        "answer": "no",
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    dataset = MMEBV2MetadataSmokeAdapter(dataset_root=root, dataset_id="mmeb_smoke").load()

    assert dataset.dataset_id == "mmeb_smoke"
    assert [item.id for item in dataset.corpus] == [
        "mmeb_v2_activitynetqa_answer_smoke:answer:yes",
        "mmeb_v2_activitynetqa_answer_smoke:answer:no",
    ]
    assert dataset.task_specs[0].category == "video_qa_metadata_smoke"
    assert dataset.task_specs[0].query_view == "text"
    assert dataset.qrels[dataset.queries[0].id] == [
        "mmeb_v2_activitynetqa_answer_smoke:answer:yes"
    ]
    assert dataset.metadata["benchmark_comparable"] is False


def test_config_parser_reads_toml(tmp_path: Path) -> None:
    config_path = tmp_path / "experiment.toml"
    config_path.write_text(
        """
[run]
run_id = "test_run"
top_k = 3
categories = ["text"]

[dataset]
adapter = "whisky"
catalogue_path = "products.jsonl"

[provider]
name = "mock"
dimension = 8

[limits]
queries = 2
corpus = 4

[output]
runs_root = "runs"
datasets_root = "datasets"
""".strip(),
        encoding="utf-8",
    )

    config = load_experiment_config(config_path)

    assert config.run_id == "test_run"
    assert config.dataset_adapter == "whisky"
    assert config.provider == "mock"
    assert config.provider_options["dimension"] == 8
    assert config.categories == ("text",)
    assert config.limit_queries == 2


def test_experiment_runner_writes_manifest_rankings_and_metrics(tmp_path: Path) -> None:
    dataset = RetrievalDataset(
        dataset_id="tiny",
        corpus=[
            RetrievalItem(id="d1", modality_parts=[ModalityPart(kind="text", value="apple")]),
            RetrievalItem(id="d2", modality_parts=[ModalityPart(kind="text", value="peat")]),
        ],
        queries=[RetrievalItem(id="q1", modality_parts=[ModalityPart(kind="text", value="apple")])],
        qrels={"q1": ["d1"]},
        task_specs=[
            TaskSpec(
                task_id="tiny_text",
                category="text",
                query_view="text",
                corpus_view="text",
                query_ids=["q1"],
                metrics=(1, 2),
            )
        ],
    )
    config = ExperimentConfig(
        run_id="tiny_run",
        dataset_adapter="unused",
        dataset_options={},
        provider="mock",
        provider_options={"dimension": 8},
        output_root=tmp_path / "runs",
        dataset_manifest_root=tmp_path / "datasets",
        top_k=2,
    )

    result = ExperimentRunner(
        config,
        provider=MockExperimentEmbeddingProvider(dimension=8),
        dataset=dataset,
    ).run()

    assert result.run_dir == tmp_path / "runs" / "tiny_run"
    assert (result.run_dir / "manifest.json").exists()
    assert (result.run_dir / "metrics.json").exists()
    assert (result.run_dir / "rankings.jsonl").exists()
    assert result.metrics.query_count == 1


def test_experiment_runner_respects_query_candidate_pools(tmp_path: Path) -> None:
    dataset = RetrievalDataset(
        dataset_id="candidate_pool",
        corpus=[
            RetrievalItem(id="d1", modality_parts=[ModalityPart(kind="text", value="apple")]),
            RetrievalItem(id="d2", modality_parts=[ModalityPart(kind="text", value="peat")]),
            RetrievalItem(id="d3", modality_parts=[ModalityPart(kind="text", value="smoke")]),
        ],
        queries=[RetrievalItem(id="q1", modality_parts=[ModalityPart(kind="text", value="apple")])],
        qrels={"q1": ["d1"]},
        candidate_ids={"q1": ["d1", "d2"]},
        task_specs=[
            TaskSpec(
                task_id="pool_text",
                category="text",
                query_view="text",
                corpus_view="text",
                query_ids=["q1"],
                metrics=(1, 2),
            )
        ],
    )
    config = ExperimentConfig(
        run_id="pool_run",
        dataset_adapter="unused",
        dataset_options={},
        provider="mock",
        provider_options={"dimension": 8},
        output_root=tmp_path / "runs",
        dataset_manifest_root=tmp_path / "datasets",
        top_k=2,
    )

    ExperimentRunner(
        config,
        provider=MockExperimentEmbeddingProvider(dimension=8),
        dataset=dataset,
    ).run()

    rows = [
        json.loads(line)
        for line in (tmp_path / "runs" / "pool_run" / "rankings.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    assert {row["corpus_id"] for row in rows} <= {"d1", "d2"}
    assert all(row["candidate_count"] == 2 for row in rows)


def test_qwen_vllm_provider_uses_lazy_llm_and_validates_shape() -> None:
    class FakeTokenizer:
        def apply_chat_template(self, conversation, *, tokenize: bool, add_generation_prompt: bool):
            assert not tokenize
            assert add_generation_prompt
            assert conversation[0]["role"] == "system"
            return "formatted prompt"

    class FakeLLM:
        llm_engine = types.SimpleNamespace(tokenizer=FakeTokenizer())

        def embed(self, payloads):
            assert payloads == [{"prompt": "formatted prompt"}]
            return [types.SimpleNamespace(outputs=types.SimpleNamespace(embedding=[3.0, 4.0]))]

    provider = QwenVllmEmbeddingProvider(model_name="fake-qwen", dimension=2)
    provider._llm = FakeLLM()

    vectors = provider.encode_batch(
        [
            EmbeddingInput(
                id="q1",
                modality_parts=[ModalityPart(kind="text", value="peated whisky")],
                instruction="Retrieve matching bottles.",
            )
        ]
    )

    np.testing.assert_allclose(vectors, np.array([[0.6, 0.8]], dtype=np.float32))


def test_qwen_sentence_transformers_provider_passes_instruction_as_prompt(monkeypatch) -> None:
    calls = []

    class FakeSentenceTransformer:
        def __init__(self, model_id, **kwargs):
            assert model_id == "fake-qwen"
            assert kwargs == {"device": "cpu"}

        def encode(self, payloads, **kwargs):
            calls.append((payloads, kwargs))
            return np.array([[0.0, 1.0]], dtype=np.float32)

    fake_module = types.SimpleNamespace(SentenceTransformer=FakeSentenceTransformer)
    monkeypatch.setitem(sys.modules, "sentence_transformers", fake_module)
    provider = Qwen3VLEmbeddingProvider(
        model_name="fake-qwen",
        dimension=2,
        runtime="sentence-transformers",
        batch_size=4,
        device="cpu",
    )

    vectors = provider.encode_batch(
        [
            EmbeddingInput(
                id="q1",
                modality_parts=[ModalityPart(kind="text", value="peated whisky")],
                instruction="Retrieve matching bottles.",
            )
        ]
    )

    assert calls == [
        (
            ["peated whisky"],
            {
                "batch_size": 4,
                "normalize_embeddings": True,
                "prompt": "Retrieve matching bottles.",
            },
        )
    ]
    np.testing.assert_allclose(vectors, np.array([[0.0, 1.0]], dtype=np.float32))


def test_qwen_official_provider_puts_instruction_in_payload(monkeypatch) -> None:
    calls = []

    class FakeOfficialEmbedder:
        def __init__(self, model_name_or_path, **kwargs):
            assert model_name_or_path == "fake-qwen"
            assert kwargs == {"max_length": 16384}

        def process(self, payloads):
            calls.append(payloads)
            return np.array([[3.0, 4.0]], dtype=np.float32)

    fake_module = types.SimpleNamespace(Qwen3VLEmbedder=FakeOfficialEmbedder)
    monkeypatch.setitem(sys.modules, "scripts.qwen3_vl_embedding", fake_module)
    provider = Qwen3VLEmbeddingProvider(
        model_name="fake-qwen",
        dimension=2,
        runtime="official",
        normalize=True,
        max_length=16384,
    )

    vectors = provider.encode_batch(
        [
            EmbeddingInput(
                id="q1",
                modality_parts=[
                    ModalityPart(kind="text", value="find the matching image"),
                    ModalityPart(kind="image", value="query.jpg"),
                ],
                instruction="Retrieve images matching the query.",
            )
        ]
    )

    assert calls == [
        [
            {
                "text": "find the matching image",
                "image": "query.jpg",
                "instruction": "Retrieve images matching the query.",
            }
        ]
    ]
    np.testing.assert_allclose(vectors, np.array([[0.6, 0.8]], dtype=np.float32))


def test_download_mmeb_v2_uses_hf_snapshot_with_metadata_profile(
    tmp_path: Path,
    monkeypatch,
) -> None:
    calls = []

    def fake_snapshot_download(**kwargs):
        calls.append(kwargs)
        return str(tmp_path / "hf-repo")

    fake_module = types.SimpleNamespace(snapshot_download=fake_snapshot_download)
    monkeypatch.setitem(sys.modules, "huggingface_hub", fake_module)

    result = download_mmeb_v2(
        MMEBV2DownloadConfig(local_dir=tmp_path / "mmeb-v2" / "hf-repo", profile="metadata")
    )

    assert result.allow_patterns == ("README.md", "dataset_setup.py", "video-tasks/data/*.jsonl")
    assert calls[0]["repo_id"] == "TIGER-Lab/MMEB-V2"
    assert calls[0]["repo_type"] == "dataset"
    assert calls[0]["local_dir"] == tmp_path / "mmeb-v2" / "hf-repo"
    assert (tmp_path / "mmeb-v2" / "download_manifest.json").exists()


def test_download_mmeb_v2_vlm2vec_profile_gets_eval_archives(
    tmp_path: Path,
    monkeypatch,
) -> None:
    calls = []

    def fake_snapshot_download(**kwargs):
        calls.append(kwargs)
        return str(tmp_path / "vlm2vec_eval")

    fake_module = types.SimpleNamespace(snapshot_download=fake_snapshot_download)
    monkeypatch.setitem(sys.modules, "huggingface_hub", fake_module)

    result = download_mmeb_v2(
        MMEBV2DownloadConfig(
            local_dir=tmp_path / "mmeb-v2" / "vlm2vec_eval",
            profile="vlm2vec-eval",
        )
    )

    assert result.allow_patterns is not None
    assert "image-tasks/*.tar.gz" in result.allow_patterns
    assert "visdoc-tasks/*.tar.gz" in result.allow_patterns
    assert "video-tasks/frames/*.tar.gz-*" in result.allow_patterns
    assert calls[0]["allow_patterns"] == list(result.allow_patterns)


def test_setup_mmeb_v2_vlm2vec_eval_unpacks_official_layout(tmp_path: Path) -> None:
    root = tmp_path / "mmeb-v2" / "vlm2vec_eval"
    image_tasks = root / "image-tasks"
    frames = root / "video-tasks" / "frames"
    visdoc_tasks = root / "visdoc-tasks"
    image_tasks.mkdir(parents=True)
    frames.mkdir(parents=True)
    visdoc_tasks.mkdir(parents=True)
    _write_tar(image_tasks / "mmeb_v1.tar.gz", {"MMEB/OK-VQA/image1.png": b"image"})
    _write_tar(frames / "video_cls.tar.gz", {"UCF101/video_1/frame1.png": b"frame"})
    _write_tar(frames / "video_mret.tar.gz", {"video_mret/QVHighlight/video_1/frame1.png": b"frame"})
    _write_tar(frames / "video_ret.tar.gz", {"MSR-VTT/video_1/frame1.png": b"frame"})
    _write_tar(frames / "video_qa.tar.gz-00", {"video_qa/ActivityNetQA/video_1/frame1.png": b"frame"})
    _write_tar(visdoc_tasks / "visdoc-tasks.images.tar.gz", {"VIDORE/doc1/page1.png": b"image"})

    result = setup_mmeb_v2_vlm2vec_eval(
        MMEBV2Vlm2VecSetupConfig(local_dir=root, download=False)
    )

    assert (image_tasks / "OK-VQA" / "image1.png").exists()
    assert (frames / "video_cls" / "UCF101" / "video_1" / "frame1.png").exists()
    assert (frames / "video_mret" / "QVHighlight" / "video_1" / "frame1.png").exists()
    assert (frames / "video_ret" / "MSR-VTT" / "video_1" / "frame1.png").exists()
    assert (frames / "video_qa" / "ActivityNetQA" / "video_1" / "frame1.png").exists()
    assert (visdoc_tasks / "VIDORE" / "doc1" / "page1.png").exists()
    assert result.manifest_path.exists()
    assert set(result.unpacked) == {
        "mmeb_v1",
        "video_cls",
        "video_mret",
        "video_ret",
        "video_qa",
        "visdoc_images",
    }


def _write_tar(path: Path, members: dict[str, bytes]) -> None:
    with tarfile.open(path, "w:gz") as archive:
        for name, payload in members.items():
            data_path = path.parent / name
            data_path.parent.mkdir(parents=True, exist_ok=True)
            data_path.write_bytes(payload)
            archive.add(data_path, arcname=name)
