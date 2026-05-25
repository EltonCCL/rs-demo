# Codex Agent Handoff

This is the start-here note for a new Codex agent working on the project from an SSH server.

## Project Frame

This project is a whisky **similarity search** and retrieval benchmark, not a recommendation
system. We do not have user profiles, ratings, clicks, purchases, or preference labels. The goal is
to test whether text, image, and multimodal product representations retrieve the catalogue products
that match a query.

The main experiment compares two retrieval families:

| Family | What is ranked |
|---|---|
| Direct dense embedding retrieval | Local NumPy product embeddings ranked by cosine similarity. |
| Google File Search RAG | Managed File Search retrieval plus Gemini JSON ranking. |

There is now a separate benchmark-reproduction track for multimodal embedding models on MMEB-V2.
For benchmark scores, prefer official benchmark/model evaluators over reimplementing loaders and
metrics in `rs_demo`.

## First Commands

From the repository root:

```bash
conda env create -f environment.yml
conda activate rs-demo
pip install -r requirements-dev.txt
pytest -q
ruff check .
```

If the conda environment already exists:

```bash
conda activate rs-demo
pip install -r requirements-dev.txt
pytest -q
ruff check .
```

Use the package CLI from the repository root:

```bash
python -m rs_demo --help
```

## Important Files

| Purpose | Path |
|---|---|
| Main README and documentation map | `README.md` |
| End-to-end CLI sequence | `docs/pipeline.md` |
| RAG design, commands, store names, and current metrics | `docs/rag_approach.md` |
| Query labels and thumbnails | `docs/evaluation_queries_and_labels.md` |
| Embedding experiments and MMEB-V2 benchmark notes | `docs/experiment_framework.md` |
| Raw PDF/parser caveats | `docs/raw_data_characteristics.md` |
| Core library code | `src/rs_demo/` |
| Test suite | `tests/` |

## MMEB-V2 / Qwen Benchmark Status

The Qwen3-VL-Embedding-2B MMEB-V2 reproduction has completed successfully using the official Qwen
evaluator in:

```text
external/repos/Qwen3-VL-Embedding/
```

Do not treat `src/rs_demo/experiments/` as the source of truth for this benchmark. The local
experiment runner is useful for smoke tests and custom whisky/query-set work, but official MMEB-V2
scores should come from the Qwen evaluator or an evaluator that reuses the same task loaders and
metrics.

Local MMEB-V2 assets are prepared under:

```text
data/external/mmeb-v2/vlm2vec_eval/
```

This tree is large, about 315 GB after image, video, and VisDoc assets are downloaded/unpacked.
The setup manifest is:

```text
data/external/mmeb-v2/vlm2vec_eval_setup_manifest.json
```

Completed Qwen output is:

```text
data/experiments/qwen3_mmeb_v2_results/Qwen3-VL-Embedding-2B/
```

Key files:

```text
summary.tsv
details.tsv
image/*_score.json
video/*_score.json
visdoc/*_score.json
```

Final Qwen3-VL-Embedding-2B scores:

| Split | Score |
|---|---:|
| Image | 74.9 |
| Video | 62.2 |
| VisDoc | 79.2 |
| All | 73.3 |

These reproduce the reported Qwen table closely (`Image 75.0`, `Video 61.9`, `VisDoc 79.2`,
`All 73.2`). The full run used all 8 local RTX 4090 GPUs via `CUDA_VISIBLE_DEVICES=0,1,2,3,4,5,6,7`.
Use fewer visible GPUs if the user needs GPUs for other work.

The helper script for monitoring progress is:

```bash
watch -n 60 ./scripts/watch_qwen_mmeb_progress.sh
```

It is still useful for checking whether all 78 score files are present, even after completion.

Local Qwen evaluator changes made during setup:

- `external/repos/Qwen3-VL-Embedding/src/evaluation/mmeb_v2/eval_embedding.py` reads
  `QWEN_ATTN_IMPLEMENTATION`, allowing `sdpa` because `flash_attn` is not installed.
- Two Qwen vision utility files lazily/fallback-import `torchvision.io.write_video` because the
  installed `torchvision` no longer exposes it.
- `external/repos/Qwen3-VL-Embedding/scripts/evaluation/mmeb_v2/eval_embedding.sh` accepts
  `BATCH_SIZE`, `MODALITIES`, `DATA_BASEDIR`, and `OUTPUT_BASEDIR` from the environment.

The successful run command was:

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

Do not set `HF_HUB_OFFLINE=1` for a first run unless the HF `datasets` metadata is already cached:
the evaluator still calls `datasets.load_dataset("ziyjiang/MMEB_Test_Instruct", ...)`.

Next benchmark task: Gemini Embedding 2 on MMEB-V2. Prefer reusing the Qwen/MMEB task definitions,
candidate construction, and scoring, replacing only the embedding call. Avoid duplicating MMEB-V2
dataset/model/metric wrappers inside `rs_demo` unless there is a specific ablation need.

## Data and Generated Artifacts

The raw PDF is expected at:

```text
data/raw/Great Whiskeys.pdf
```

It may not be committed. If it is missing, do not rerun extraction until the user provides it.

The current parsed catalogue is:

```text
data/extracted/product_parse_sample.jsonl
```

The catalogue currently contains 533 product records. The product ID is the unit of retrieval and
evaluation.

## API-Key Handling

For CLI runs, use shell environment variables:

```bash
export GOOGLE_API_KEY=...
# or
export GEMINI_API_KEY=...
```

The CLI can also read a local uncommitted `.env`, but do not rely on that for demo notebooks.

The live demo notebooks prompt for API keys inside notebook cells:

```text
notebooks/demo_01_direct_embedding_results.ipynb
notebooks/demo_02_rag_results.ipynb
```

Do not commit API keys or notebook outputs that expose keys.

## Direct Embedding Artifacts

Product embeddings are stored under:

```text
data/embeddings/gemini/
```

Expected arrays:

```text
text_embeddings.npy
image_embeddings.npy
multimodal_embeddings.npy
metadata.jsonl
manifest.json
```

Query embeddings are stored under:

```text
data/embeddings/gemini/queries/text/
data/embeddings/gemini/queries/image/
data/embeddings/gemini/queries/image_text/
data/embeddings/gemini/queries/cropped_image_text/
```

Before rebuilding real embeddings, check quota and ask the user. These API calls are slow and
quota-consuming.

## RAG Artifacts

Local RAG corpora are under:

```text
data/rag/product_text_corpus/
data/rag/product_image_corpus/
data/rag/product_multimodal_corpus/
```

Current File Search store manifests:

```text
data/rag/rag_product_text_store.json
data/rag/rag_product_image_store.json
data/rag/rag_product_multimodal_store.json
```

Current store names are documented in `docs/rag_approach.md`. File Search stores persist on
Google's side. Do not create a new store or reupload the full corpus unless the user explicitly
asks for it.

## Demo Notebooks

Use these for live demonstrations:

| Notebook | Live input | Result panels |
|---|---|---|
| `notebooks/demo_01_direct_embedding_results.ipynb` | Text query or image path | Direct embedding results. Text queries show text, image, and multimodal product vectors. Image queries show image and multimodal product vectors. |
| `notebooks/demo_02_rag_results.ipynb` | Text query or image path | RAG results. Text queries show text, image, and multimodal stores. Image queries show image and multimodal stores. |

Use these for offline inspection after batch evaluation:

```text
notebooks/gemini_review_01_text_to_product_text.ipynb
...
notebooks/gemini_review_09_cropped_image_text_to_product_multimodal.ipynb
```

The `gemini_review_*.ipynb` notebooks should not call APIs.

## Safe Development Rules

- Do not overwrite real Gemini embeddings unless the user asks.
- Do not recreate or delete File Search stores unless the user asks.
- Use `--limit-products`, `--limit-queries`, or `--max-requests` for smoke tests.
- Use `--sleep-seconds 5` for conservative RAG evaluation on free-tier keys.
- For parser changes, run `pytest -q` and `ruff check .` before handing back.
- If catalogue parsing changes, regenerate validation and review artifacts before trusting metrics.

## Common Next Tasks

| Task | Starting point |
|---|---|
| Explain the full pipeline | `docs/pipeline.md` |
| Continue RAG experiments | `docs/rag_approach.md` |
| Continue Gemini/MMEB-V2 benchmark work | `docs/experiment_framework.md` |
| Inspect benchmark query labels | `docs/evaluation_queries_and_labels.md` |
| Debug extraction/parsing | `docs/raw_data_characteristics.md` and `tests/test_product_parser.py` |
| Prepare a live demo | `notebooks/demo_01_direct_embedding_results.ipynb` and `notebooks/demo_02_rag_results.ipynb` |

