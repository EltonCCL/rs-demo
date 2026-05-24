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
| Raw PDF/parser caveats | `docs/raw_data_characteristics.md` |
| Core library code | `src/rs_demo/` |
| Test suite | `tests/` |

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
| Inspect benchmark query labels | `docs/evaluation_queries_and_labels.md` |
| Debug extraction/parsing | `docs/raw_data_characteristics.md` and `tests/test_product_parser.py` |
| Prepare a live demo | `notebooks/demo_01_direct_embedding_results.ipynb` and `notebooks/demo_02_rag_results.ipynb` |

