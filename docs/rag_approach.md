# RAG Approach and Developer Handoff

This document explains the Google File Search RAG baseline used in this project. It is meant for developers who need to continue the work without reverse-engineering the command history.

For the full end-to-end CLI pipeline, see [pipeline.md](pipeline.md). For the SSH/Codex handoff
checklist, see [agent_handoff.md](agent_handoff.md). For query labels and benchmark inputs, see
[evaluation_queries_and_labels.md](evaluation_queries_and_labels.md).

---

## Goal

The local embedding experiment ranks products by explicit vector similarity. The RAG experiment is the managed comparison:

```text
query -> Google File Search store -> Gemini generated top-k product IDs
```

This is not a raw vector benchmark. Google File Search handles retrieval internally, then the generation model reads retrieved context and emits a JSON ranking. We evaluate the generated product IDs with the same `hit@1`, `hit@5`, and `MRR` metrics used for the embedding experiment.

The purpose is to compare three product-store representations:

| Store | Product representation | Main comparison |
|---|---|---|
| Text store | One text document per product | Text query retrieval |
| Image store | One cropped/compressed product image per product | Image and image+text query retrieval |
| Multimodal store | One PDF product sheet per product with text plus image | Text, image, and image+text query retrieval |

Each store is separate. Do not reuse one File Search store for another corpus type because store contents persist and the experiment needs isolated baselines.

---

## Code Structure

Main implementation file:

```text
src/rs_demo/rag.py
```

Important classes:

| Class | Responsibility |
|---|---|
| `ProductTextRagCorpusBuilder` | Builds one `.txt` file per product. |
| `ProductImageRagCorpusBuilder` | Builds one compressed `.jpg` file per product image. |
| `ProductMultimodalRagCorpusBuilder` | Builds one compact `.pdf` sheet per product with text and bottle image. |
| `RagTextStoreIngestionPipeline` | Creates or resumes a File Search store upload from a corpus manifest. |
| `GeminiFileSearchClient` | Wraps Google File Search store creation, upload, and query calls. |
| `RagTextEvaluationPipeline` | Runs text, image, and image+text eval queries against a store. |
| `parse_rag_ranked_products` | Parses Gemini JSON output and normalizes returned product IDs. |

CLI entry point:

```text
src/rs_demo/cli.py
```

Tests:

```text
tests/test_rag.py
tests/test_cli.py
```

---

## Product-Level Store Design

The unit of retrieval is always one catalogue product.

This matters because the evaluation labels use `product_id`, not pages, brands, or files. Every corpus builder writes one file per product and records the mapping in a manifest.

### Text Store

Command:

```bash
python -m rs_demo build-rag-text-corpus
```

Output:

```text
data/rag/product_text_corpus/*.txt
data/rag/product_text_corpus/manifest.jsonl
```

Each text file contains:

```text
title: <product name>
product_id: <product id>
text:
<structured product text>
```

The structured text is produced by `build_product_text(record)` and includes metadata, tasting description, and brand context.

### Image Store

Command:

```bash
python -m rs_demo build-rag-image-corpus
```

Output:

```text
data/rag/product_image_corpus/*.jpg
data/rag/product_image_corpus/manifest.jsonl
```

Each product image is taken from:

```text
cropped_product_image_path
```

with fallback to:

```text
product_image_path
```

The image builder recompresses images to JPEG with a bounded maximum dimension. This keeps the full 533-product corpus small enough for File Search upload.

Current generated size:

```text
533 product JPEGs
about 24 MB total
```

### Multimodal Store

Command:

```bash
python -m rs_demo build-rag-multimodal-corpus
```

Output:

```text
data/rag/product_multimodal_corpus/*.pdf
data/rag/product_multimodal_corpus/manifest.jsonl
```

Each PDF contains:

- Product title.
- Product ID.
- Structured metadata and descriptions.
- Brand/distillery context.
- Cropped bottle image embedded in the PDF.

Current generated size:

```text
533 product PDFs
about 23 MB total
```

This is the closest managed-File-Search analogue to the local product multimodal embedding.

---

## Store Creation and Upload

Store creation uses:

```text
models/gemini-embedding-2
```

The generation model used for query-time JSON ranking has been:

```text
gemini-3.1-flash-lite
```

The upload pipeline writes the store manifest incrementally. If the process is interrupted or transient network errors happen, rerun the same command. Completed uploads are skipped and failed/missing records are retried.

### Text Store

```bash
python -m rs_demo create-rag-text-store \
  --concurrency 5 \
  --progress-every 25
```

Manifest:

```text
data/rag/rag_product_text_store.json
```

Current store:

```text
fileSearchStores/ragproducttextstore-tc02qz6qfvei
```

### Image Store

```bash
python -m rs_demo create-rag-image-store \
  --concurrency 5 \
  --progress-every 25
```

Manifest:

```text
data/rag/rag_product_image_store.json
```

Current store:

```text
fileSearchStores/ragproductimagestore-dppy5hhkl8n5
```

### Multimodal Store

```bash
python -m rs_demo create-rag-multimodal-store \
  --concurrency 5 \
  --progress-every 25
```

Manifest:

```text
data/rag/rag_product_multimodal_store.json
```

Current store:

```text
fileSearchStores/ragproductmultimodalstore-fdfd4rlokjnp
```

---

## Query Evaluation

All RAG evaluation commands eventually call:

```text
RagTextEvaluationPipeline
```

Despite the name, it supports:

- `query_type: "text"`
- `query_type: "image"`
- `query_type: "image_text"`

For image and image+text queries, the attached query image is sent as an input part to Gemini. File Search is attached as a tool. The prompt asks Gemini to return JSON only:

```json
{"results":[{"rank":1,"product_id":"...","product_name":"...","reason":"..."}]}
```

The parser normalizes product IDs returned as filenames, for example:

```text
p0244-the-macallan-30-year-old.jpg -> p0244-the-macallan-30-year-old
p0267-nikka-all-malt.pdf -> p0267-nikka-all-malt
```

This is needed because File Search sometimes exposes document filenames instead of manifest metadata.

---

## Current Experiment Matrix

### Text Store

```bash
python -m rs_demo run-rag-text-evaluation \
  --store-manifest data/rag/rag_product_text_store.json \
  --queries data/eval/text_queries.jsonl \
  --out data/eval/gemini_rag_text_report.json \
  --top-k 5 \
  --model gemini-3.1-flash-lite \
  --sleep-seconds 5
```

Output summary:

```text
data/eval/gemini_rag_text_query_summary.md
```

### Image Store

```bash
python -m rs_demo run-rag-evaluation \
  --store-manifest data/rag/rag_product_image_store.json \
  --queries data/eval/image_queries.jsonl \
  --out data/eval/gemini_rag_image_image_report.json \
  --report-key rag_image_image \
  --top-k 5 \
  --model gemini-3.1-flash-lite \
  --sleep-seconds 5 \
  --continue-on-error

python -m rs_demo run-rag-evaluation \
  --store-manifest data/rag/rag_product_image_store.json \
  --queries data/eval/image_text_queries.jsonl \
  --out data/eval/gemini_rag_image_image_text_report.json \
  --report-key rag_image_image_text \
  --top-k 5 \
  --model gemini-3.1-flash-lite \
  --sleep-seconds 5 \
  --continue-on-error

python -m rs_demo run-rag-evaluation \
  --store-manifest data/rag/rag_product_image_store.json \
  --queries data/eval/cropped_image_text_queries.jsonl \
  --out data/eval/gemini_rag_image_cropped_image_text_report.json \
  --report-key rag_image_cropped_image_text \
  --top-k 5 \
  --model gemini-3.1-flash-lite \
  --sleep-seconds 5 \
  --continue-on-error
```

Output summary:

```text
data/eval/gemini_rag_image_query_summary.md
```

### Multimodal Store

```bash
python -m rs_demo run-rag-evaluation \
  --store-manifest data/rag/rag_product_multimodal_store.json \
  --queries data/eval/text_queries.jsonl \
  --out data/eval/gemini_rag_multimodal_text_report.json \
  --report-key rag_multimodal_text \
  --top-k 5 \
  --model gemini-3.1-flash-lite \
  --sleep-seconds 5 \
  --continue-on-error

python -m rs_demo run-rag-evaluation \
  --store-manifest data/rag/rag_product_multimodal_store.json \
  --queries data/eval/image_queries.jsonl \
  --out data/eval/gemini_rag_multimodal_image_report.json \
  --report-key rag_multimodal_image \
  --top-k 5 \
  --model gemini-3.1-flash-lite \
  --sleep-seconds 5 \
  --continue-on-error

python -m rs_demo run-rag-evaluation \
  --store-manifest data/rag/rag_product_multimodal_store.json \
  --queries data/eval/image_text_queries.jsonl \
  --out data/eval/gemini_rag_multimodal_image_text_report.json \
  --report-key rag_multimodal_image_text \
  --top-k 5 \
  --model gemini-3.1-flash-lite \
  --sleep-seconds 5 \
  --continue-on-error

python -m rs_demo run-rag-evaluation \
  --store-manifest data/rag/rag_product_multimodal_store.json \
  --queries data/eval/cropped_image_text_queries.jsonl \
  --out data/eval/gemini_rag_multimodal_cropped_image_text_report.json \
  --report-key rag_multimodal_cropped_image_text \
  --top-k 5 \
  --model gemini-3.1-flash-lite \
  --sleep-seconds 5 \
  --continue-on-error
```

Output summary:

```text
data/eval/gemini_rag_multimodal_query_summary.md
```

---

## Latest RAG Results Snapshot

These are the latest generated reports at the time this handoff was written.

| Setting | Queries | Hit@1 | Hit@5 | MRR | Valid ID Rate |
|---|---:|---:|---:|---:|---:|
| Text -> text RAG store | 20 | 0.8000 | 0.9000 | 0.8292 | 1.0000 |
| Text -> multimodal RAG store | 20 | 0.7000 | 0.8500 | 0.7517 | 1.0000 |
| Image -> image RAG store | 22 | 0.8182 | 0.8182 | 0.8182 | 1.0000 |
| Image -> multimodal RAG store | 22 | 0.6818 | 0.6818 | 0.6818 | 0.9762 |
| Whole image + text -> image RAG store | 11 | 0.7273 | 0.7273 | 0.7273 | 1.0000 |
| Whole image + text -> multimodal RAG store | 11 | 0.7273 | 0.7273 | 0.7273 | 0.7778 |
| Cropped image + text -> image RAG store | 11 | 0.8182 | 0.8182 | 0.8182 | 1.0000 |
| Cropped image + text -> multimodal RAG store | 11 | 0.5455 | 0.5455 | 0.5455 | 0.8077 |

Use the JSON reports as the source of truth. The snapshot above is for orientation only.

---

## Practical Notes

### API Keys

For CLI runs, set one of these in the shell environment:

```text
GOOGLE_API_KEY=...
GEMINI_API_KEY=...
```

The CLI can also read a local uncommitted `.env`. The live demo notebooks instead prompt for
API keys inside notebook cells and do not read `.env`.

### Rate Limits

For evaluation, keep:

```text
--sleep-seconds 5
```

This is intentionally conservative for free-tier API limits. If a run fails with a transient transport error, use:

```text
--continue-on-error
--max-retries 5
--retry-sleep-seconds 20
```

### Upload Failures

Common upload failures are transient network errors such as connection reset, timeout, or no route to host. The upload manifest is resumable, so rerun the same `create-rag-*-store` command. The pipeline retries only missing or failed records.

### Evaluation Resume

Evaluation reports are also resumable by default. If a query file or parser behavior changed and you need a clean run, pass:

```text
--no-resume
```

### File Search Store Persistence

File Search stores persist on Google's side. Create a new store for a new corpus definition. Reusing an old store after changing corpus files can silently mix old and new experiment conditions.

---

## Extending the RAG Baseline

When adding a new RAG experiment:

1. Decide the product-store representation.
2. Add a corpus builder if the representation is new.
3. Ensure one file maps to one `product_id`.
4. Write a manifest through `RagProductDocument.to_manifest_record`.
5. Reuse `RagTextStoreIngestionPipeline` for upload.
6. Reuse `RagTextEvaluationPipeline` for evaluation.
7. Add a unique `report_key`.
8. Add tests for corpus generation, CLI parsing, and product-ID parsing edge cases.
9. Run `pytest -q` and `ruff check .`.

Avoid adding custom one-off scripts for new RAG experiments unless they are only for summary rendering. The main RAG logic should stay in `src/rs_demo/rag.py` and be reachable from `python -m rs_demo`.
