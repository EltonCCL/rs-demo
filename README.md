# Whisky Similarity Search Demo

Small research/demo codebase for a **product-level** whisky catalogue and retrieval benchmark from a single PDF: extraction, parsing, image crops, validation, Markdown review, Gemini Embedding 2 vectors, and retrieval evaluation.

Target query modes: **text**, **image**, and **text + image**.

This is currently framed as **similarity search**, not a recommendation system. We do not have user profiles, clicks, purchases, ratings, or preference labels. The experiment therefore tests whether multimodal embeddings retrieve catalogue products that match a query, rather than whether they personalize recommendations for a user.

---

## Documentation map

| What you need | Where to go |
|----------------|-------------|
| **CLI pipeline** — extract → parse → crop → validate → Markdown → mock/Gemini embeddings → evaluation, with paths and outputs | [docs/pipeline.md](docs/pipeline.md) |
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

For real Gemini embeddings, put one of these variables in a local `.env` or shell environment:

```bash
GOOGLE_API_KEY=...
# or
GEMINI_API_KEY=...
```

Do not commit `.env`.

---

## Current stage

High level:

```text
PDF → page text/images → product records → validation → review Markdown
  → product/query embeddings → retrieval evaluation → notebook/report review
```

The mock embedding path is still available as a deterministic local sanity check. The main experiment now uses Gemini Embedding 2 with three product indexes: product text, product image, and product multimodal. See [docs/pipeline.md](docs/pipeline.md) for the full command sequence and file outputs.

---

## Evaluation seeds

Controlled labels live under `data/eval/`:

- `text_queries.jsonl`: 20 natural-language product requests.
- `image_queries.jsonl`: 22 image-only queries, split into 11 cropped bottle images and 11 whole-scene images.
- `image_text_queries.jsonl`: 11 whole-scene images plus the fixed question, “What is the whisky in this image?”
- `cropped_image_text_queries.jsonl`: 11 cropped bottle images plus the same fixed question.

These are **not** full human relevance judgments. They are controlled positives from catalogue metadata, tasting notes, and manually reviewed scene references. A readable catalogue of queries and positives is in [docs/evaluation_queries_and_labels.md](docs/evaluation_queries_and_labels.md).

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
| 7 | Whole image + text → product multimodal | [gemini_review_07_image_text_to_product_multimodal.ipynb](notebooks/gemini_review_07_image_text_to_product_multimodal.ipynb) |
| 8 | Cropped image + text → product image | [gemini_review_08_cropped_image_text_to_product_image.ipynb](notebooks/gemini_review_08_cropped_image_text_to_product_image.ipynb) |
| 9 | Cropped image + text → product multimodal | [gemini_review_09_cropped_image_text_to_product_multimodal.ipynb](notebooks/gemini_review_09_cropped_image_text_to_product_multimodal.ipynb) |

The same table appears in [docs/evaluation_queries_and_labels.md](docs/evaluation_queries_and_labels.md) (regenerate that file with `python scripts/render_evaluation_query_docs.py` after changing queries or images).
