# Whisky Recommendation Demo

Small research/demo codebase for a **product-level** whisky catalogue and retrieval benchmarks from a single PDF: extraction, parsing, crops, validation, Markdown review, then mock (and later real) embeddings and evaluation.

Target query modes: **text**, **image**, and **text + image**.

---

## Documentation map

| What you need | Where to go |
|----------------|-------------|
| **CLI pipeline** — extract → parse → crop → validate → Markdown → mock embeddings → mock eval, with paths and outputs | [docs/pipeline.md](docs/pipeline.md) |
| **Evaluation benchmark** — queries, expected positives, scene thumbnails, **Gemini ranking notebook links** | [docs/evaluation_queries_and_labels.md](docs/evaluation_queries_and_labels.md) |
| **PDF layout and parser context** — page structure, quirks, risks before changing extraction | [docs/raw_data_characteristics.md](docs/raw_data_characteristics.md) |

---

## Setup

Conda creates the environment; Python packages come from pip:

```bash
conda env create -f environment.yml
conda activate rs-demo
pip install -r requirements-dev.txt
```

If the environment already exists:

```bash
conda activate rs-demo
pip install -r requirements-dev.txt
```

Tests and lint:

```bash
pytest -q
ruff check .
```

---

## Current stage

High level:

```text
PDF → page text/images → product records → validation → review Markdown
  → mock product/query embeddings → mock retrieval evaluation
```

The mock embedding step is **deterministic** and only for exercising data layout, arrays, and retrieval code before wiring a real embedding provider. See [docs/pipeline.md](docs/pipeline.md) for the full command sequence and file outputs.

---

## Evaluation seeds

Controlled labels live under `data/eval/` (`text_queries.jsonl`, `image_queries.jsonl`, `image_text_queries.jsonl`, plus movie-scene images). They are **not** full human relevance judgments. A readable catalogue of queries and positives is in [docs/evaluation_queries_and_labels.md](docs/evaluation_queries_and_labels.md).

---

## Parser and catalogue notes

The parser is **heuristic** and specific to this PDF (multi-product pages, continuation metadata, rare styles, and so on). Known risks include OCR-like typos, approximate image-to-product association, and records that still need manual validation. Deeper notes: [docs/raw_data_characteristics.md](docs/raw_data_characteristics.md).

---

## Jupyter: Gemini retrieval review

After Gemini evaluation, browse **real rankings** offline (loads `data/eval/gemini_retrieval_report.json` and local embeddings). One notebook per retrieval setting:

| # | Setting | Notebook |
|---|---------|----------|
| 1 | Text → product text | [gemini_review_01_text_to_product_text.ipynb](notebooks/gemini_review_01_text_to_product_text.ipynb) |
| 2 | Text → product multimodal | [gemini_review_02_text_to_product_multimodal.ipynb](notebooks/gemini_review_02_text_to_product_multimodal.ipynb) |
| 3 | Cropped image → product image | [gemini_review_03_cropped_image_to_product_image.ipynb](notebooks/gemini_review_03_cropped_image_to_product_image.ipynb) |
| 4 | Whole scene → product image | [gemini_review_04_whole_image_to_product_image.ipynb](notebooks/gemini_review_04_whole_image_to_product_image.ipynb) |
| 5 | Cropped image → product multimodal | [gemini_review_05_cropped_image_to_product_multimodal.ipynb](notebooks/gemini_review_05_cropped_image_to_product_multimodal.ipynb) |
| 6 | Whole scene → product multimodal | [gemini_review_06_whole_image_to_product_multimodal.ipynb](notebooks/gemini_review_06_whole_image_to_product_multimodal.ipynb) |
| 7 | Image + text → product multimodal | [gemini_review_07_image_text_to_product_multimodal.ipynb](notebooks/gemini_review_07_image_text_to_product_multimodal.ipynb) |

The same table appears in [docs/evaluation_queries_and_labels.md](docs/evaluation_queries_and_labels.md) (regenerate that file with `python scripts/render_evaluation_query_docs.py` after changing queries or images).
