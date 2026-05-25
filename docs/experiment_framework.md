# Flexible Embedding Experiments

This layer is for direct embedding retrieval experiments across multiple datasets and models. It is
additive: the existing mock/Gemini whisky commands and RAG commands still work as before.

Current design rule: use `rs_demo` for custom whisky/query-set experiments and smoke tests, but use
official benchmark runners for benchmark reproduction whenever possible. MMEB-V2 scores are sensitive
to task loaders, candidate pools, visual preprocessing, and aggregation; duplicating those pieces in a
generic local runner creates unnecessary comparability risk.

## Data Layout

Keep third-party data preserved. If a local third-party checkout needs runtime patches, document them
instead of treating the checkout as an upstream-clean source:

```text
data/external/mmeb-v2/                 # MMEB-V2 assets or HF exports
external/repos/VLM2Vec/                # optional cloned VLM2Vec checkout
external/repos/Qwen3-VL-Embedding/     # optional cloned Qwen checkout
```

Generated experiment artifacts are ignored by git:

```text
data/experiments/runs/<run_id>/
data/experiments/datasets/<dataset_id>/
data/experiments/qwen3_mmeb_v2_results/
```

Each embedding view is stored as:

```text
embeddings/<dataset>/<model>/<split>/<view>/vectors.npy
embeddings/<dataset>/<model>/<split>/<view>/items.jsonl
embeddings/<dataset>/<model>/<split>/<view>/manifest.json
```

## Completed Qwen MMEB-V2 Reproduction

Qwen3-VL-Embedding-2B was run on all 78 MMEB-V2 tasks with the official Qwen evaluator:

```text
external/repos/Qwen3-VL-Embedding/
```

Final outputs:

```text
data/experiments/qwen3_mmeb_v2_results/Qwen3-VL-Embedding-2B/summary.tsv
data/experiments/qwen3_mmeb_v2_results/Qwen3-VL-Embedding-2B/details.tsv
data/experiments/qwen3_mmeb_v2_results/Qwen3-VL-Embedding-2B/{image,video,visdoc}/*_score.json
```

Summary:

| Category | Score |
|---|---:|
| IMG_CLS(10) | 70.3 |
| IMG_QA(10) | 74.3 |
| IMG_RET(12) | 74.8 |
| IMG_GRD(4) | 88.4 |
| IMG(36) | 74.9 |
| VID(18) | 62.2 |
| Visdoc(24) | 79.2 |
| ALL(78) | 73.3 |

This closely matches the expected Qwen3-VL-Embedding-2B report (`Image 75.0`, `Video 61.9`,
`VisDoc 79.2`, `All 73.2`).

The successful command was:

```bash
cd external/repos/Qwen3-VL-Embedding
env -u ALL_PROXY -u all_proxy \
  -u HTTP_PROXY -u http_proxy \
  -u HTTPS_PROXY -u https_proxy \
  -u NO_PROXY -u no_proxy \
  CUDA_VISIBLE_DEVICES=0,1,2,3,4,5,6,7 \
  QWEN_ATTN_IMPLEMENTATION=sdpa \
  BATCH_SIZE=4 \
  DATA_BASEDIR=/home/elton/rs-demo/data/external/mmeb-v2/vlm2vec_eval \
  OUTPUT_BASEDIR=/home/elton/rs-demo/data/experiments/qwen3_mmeb_v2_results \
  MASTER_PORT=2278 \
  conda run -n rs-demo bash scripts/evaluation/mmeb_v2/eval_embedding.sh \
  Qwen/Qwen3-VL-Embedding-2B
```

Notes:

- The run used all 8 visible GPUs. Restrict `CUDA_VISIBLE_DEVICES` for smaller runs.
- `BATCH_SIZE=4` was conservative for RTX 4090 memory. Batch size changes speed, not retrieval
  metrics.
- `HF_HUB_OFFLINE=1` caused the first full launch to fail because the evaluator still loads
  annotation/instruction datasets from Hugging Face at runtime.
- `flash_attn` is not installed in `rs-demo`, so the local Qwen evaluator was patched to allow
  `QWEN_ATTN_IMPLEMENTATION=sdpa`.
- The result monitor is `scripts/watch_qwen_mmeb_progress.sh`.

Use these results as the baseline when adding Gemini Embedding 2 to the same benchmark.

## Next: Gemini Embedding 2 on MMEB-V2

The recommended Gemini-MMEB implementation is not a full rewrite of the benchmark framework. Reuse
the official Qwen/MMEB task YAMLs, data loading semantics, candidate construction, and scoring. Swap
only the embedding function so Gemini produces query and candidate vectors for the same examples.

Practical direction:

- Treat `external/repos/Qwen3-VL-Embedding/src/evaluation/mmeb_v2/` as the benchmark reference
  implementation.
- Build a small Gemini embedding adapter that can consume the same collated examples and write the
  same `<task>_qry`, `<task>_tgt`, `<task>_info.jsonl`, `<task>_pred.jsonl`, and `<task>_score.json`
  artifacts.
- Keep `summary.tsv` and `details.tsv` generation compatible with Qwen's `gather_results` script.
- Start with image tasks or a small subset before paying for all 78 tasks.
- Record API model name, rate limits, retry policy, and whether images/videos/doc pages were sent
  directly or reduced to sampled frames/pages.

Avoid copying MMEB-V2 into `src/rs_demo/experiments/` unless the user explicitly wants an independent
benchmark implementation. The local package should orchestrate, cache, and report; the benchmark
reference should define the task semantics.

## Run A Smoke Experiment

The checked-in configs use the deterministic mock provider by default, so they are safe offline:

```bash
python -m rs_demo run-experiment experiments/configs/whisky_gemini_qwen.toml
```

Outputs:

```text
data/experiments/runs/whisky_mock_smoke/manifest.json
data/experiments/runs/whisky_mock_smoke/metrics.json
data/experiments/runs/whisky_mock_smoke/rankings.jsonl
```

## Providers

Provider IDs:

| Provider | Notes |
|---|---|
| `mock` | Deterministic local provider for tests and smoke runs. |
| `gemini_embedding_2` | Wraps Gemini Embedding 2. Requires `GOOGLE_API_KEY` or `GEMINI_API_KEY`. |
| `qwen3_vl_embedding` | Optional local Qwen3-VL-Embedding provider. Install optional deps first. |
| `qwen3_vl_embedding_vllm` | Qwen3-VL-Embedding through vLLM's local pooling runner. |
| `vlm2vec_v2` | Integration boundary for a cloned VLM2Vec/VLM2Vec-V2 checkout. |

Optional Qwen dependencies:

```bash
pip install -e '.[qwen]'
```

Optional vLLM dependencies:

```bash
pip install -e '.[qwen-vllm]'
```

Small Qwen smoke run after installing optional dependencies:

```bash
TRANSFORMERS_OFFLINE=1 HF_HUB_OFFLINE=1 CUDA_VISIBLE_DEVICES=0 \
  python -m rs_demo run-experiment experiments/configs/whisky_qwen2b_smoke.toml
```

The equivalent tiny 8B smoke config is:

```bash
TRANSFORMERS_OFFLINE=1 HF_HUB_OFFLINE=1 CUDA_VISIBLE_DEVICES=0 \
  python -m rs_demo run-experiment experiments/configs/whisky_qwen8b_smoke.toml
```

Tiny Qwen run against the local MMEB-V2 metadata profile:

```bash
TRANSFORMERS_OFFLINE=1 HF_HUB_OFFLINE=1 CUDA_VISIBLE_DEVICES=0 \
  python -m rs_demo run-experiment experiments/configs/mmeb_v2_qwen2b_metadata_smoke.toml
```

This smoke run uses `video-tasks/data/activitynetqa.jsonl` as a text-only question-to-answer
retrieval task. It validates the external MMEB tree, adapter, Qwen provider, embedding store,
ranking, and metrics path, but it is not benchmark-comparable because visual assets are not
embedded.

Generic Qwen2B/MMEB-V2 run through `rs_demo`:

```bash
PYTHONPATH=external/repos/Qwen3-VL-Embedding:$PYTHONPATH \
TRANSFORMERS_OFFLINE=1 HF_HUB_OFFLINE=1 CUDA_VISIBLE_DEVICES=0 \
  python -m rs_demo run-experiment experiments/configs/mmeb_v2_qwen2b_benchmark.toml
```

This config expects benchmark-style MMEB-V2 records where each query has its own candidate target
pool and the first candidate is the ground-truth target when explicit positives are absent. The
runner stores these per-query candidate pools and ranks each query only against its own candidates,
which matches the MMEB formulation more closely than whole-corpus ranking.

Do not use this path for paper-score reproduction unless a task explicitly requires an ablation of
the local framework. The official Qwen evaluator above is the source of truth for Qwen/MMEB-V2
because it owns the task loaders, visual preprocessing, per-task scoring, and aggregation used by the
reported table.

Small Qwen vLLM smoke run:

```bash
python -m rs_demo run-experiment experiments/configs/whisky_qwen2b_vllm_smoke.toml
```

## Datasets

Dataset adapter IDs:

| Adapter | Source |
|---|---|
| `whisky` | Current product catalogue plus `data/eval/*.jsonl`. |
| `mmeb_v2` | Local preserved MMEB-V2-style JSON/JSONL files under `data/external/mmeb-v2/`. |
| `mmeb_v2_metadata_smoke` | Text-only smoke adapter for MMEB-V2 metadata-profile QA files. |

The MMEB-V2 adapter is a bridge, not a copy step. It scans local JSON/JSONL task files and maps common
retrieval fields into corpus/query/qrel records while preserving asset paths under the external tree.
For MMEB-style candidate-ranking files, it also records `candidate_ids` per query. Explicit
`positives`/`negatives` fields are respected; if a record only has `candidates`, candidate 0 is treated
as the ground truth following the MMEB evaluation convention.
The `metadata` download profile is useful for inspecting the official tree, but it does not contain
enough assets/test qrels for a real MMEB-V2 retrieval run.

MMEB-V2 download helpers:

```bash
pip install -e '.[mmeb]'
python -m rs_demo download-mmeb-v2 --profile metadata
```

To mirror the VLM2Vec evaluation asset layout under this repo:

```bash
env -u ALL_PROXY -u all_proxy \
  -u HTTP_PROXY -u http_proxy \
  -u HTTPS_PROXY -u https_proxy \
  -u NO_PROXY -u no_proxy \
  python -m rs_demo setup-mmeb-v2-vlm2vec
```

This prepares:

```text
data/external/mmeb-v2/vlm2vec_eval/
```

with the paths expected by VLM2Vec's `experiments/public/eval/image.yaml`,
`video.yaml`, and `visdoc.yaml`. The setup follows the reference repository's
[`experiments/public/data/download_data.sh`](https://github.com/TIGER-AI-Lab/VLM2Vec/blob/main/experiments/public/data/download_data.sh):
it downloads the MMEB-V2 eval asset archives from Hugging Face and unpacks `image-tasks/mmeb_v1.tar.gz`,
the video frame archives, and `visdoc-tasks/visdoc-tasks.images.tar.gz`. Many image/video/VisDoc query
and qrel records are still loaded by VLM2Vec/Qwen from task-specific Hugging Face datasets at
evaluation time, so a fully offline run also needs the HF dataset cache populated.

Download profiles:

| Profile | Notes |
|---|---|
| `metadata` | Small smoke profile: README, setup helper, and local JSONL metadata where available. |
| `image-smoke` | Downloads the MMEB-V1 image asset archive; still several GB. |
| `vlm2vec-eval` | Downloads the official eval asset archives used by VLM2Vec/Qwen public eval YAMLs, including VisDoc images. |
| `full` | Downloads the preserved HF asset repo; currently around 157 GB. |

The downloader writes the Hugging Face snapshot under `data/external/mmeb-v2/hf-repo/` and a small
manifest beside it at `data/external/mmeb-v2/download_manifest.json`.
