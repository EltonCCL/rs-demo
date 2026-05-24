# Pipeline and tooling

Step-by-step CLI flow from the PDF through product extraction, mock embeddings, Gemini embeddings, and retrieval evaluation. Run commands from the repository root unless noted.

For the **SSH/Codex handoff checklist**, see [agent_handoff.md](agent_handoff.md). For
**evaluation benchmark queries** (text, image, expected positives) and **links to the Gemini
ranking notebooks** (`notebooks/gemini_review_*.ipynb`), see
[evaluation_queries_and_labels.md](evaluation_queries_and_labels.md). For **Google File Search
RAG design and developer handoff**, see [rag_approach.md](rag_approach.md). For **PDF layout and
parser context**, see [raw_data_characteristics.md](raw_data_characteristics.md).

---

## Input data

Expected PDF location:

```text
data/raw/Great Whiskeys.pdf
```

The raw PDF is not committed by default. `data/raw/.gitkeep` only keeps the directory present.

---

## Code organization

Reusable pipeline code lives in:

```text
src/rs_demo/
```

The codebase is organized as a library first. Command-line access is exposed through the package CLI:

```bash
python -m rs_demo --help
```

Current library entry points:

```text
rs_demo.pdf_extraction.PdfExtractor
rs_demo.product_parser.ProductParser
rs_demo.image_cropping.ProductImageCropper
rs_demo.catalogue_validation.CatalogueValidator
rs_demo.markdown_export.ProductMarkdownExporter
rs_demo.embeddings.MockEmbeddingPipeline
rs_demo.embeddings.MockQueryEmbeddingPipeline
rs_demo.gemini_embeddings.GeminiProductEmbeddingPipeline
rs_demo.gemini_embeddings.GeminiQueryEmbeddingPipeline
rs_demo.rag.ProductTextRagCorpusBuilder
rs_demo.rag.ProductImageRagCorpusBuilder
rs_demo.rag.ProductMultimodalRagCorpusBuilder
rs_demo.rag.RagTextStoreIngestionPipeline
rs_demo.rag.RagTextEvaluationPipeline
rs_demo.queries.EvalQueryLoader
rs_demo.retrieval.ProductRetriever
rs_demo.evaluation.RetrievalEvaluator
```

This keeps the code easier to test and lets later retrieval/evaluation code call the same pipeline directly as Python classes.

---

## Full pipeline

### 1. Extract page text and images

```bash
python -m rs_demo extract-pdf data/raw/Great\ Whiskeys.pdf --max-pages 1000
```

Outputs:

```text
data/extracted/pymupdf_probe/page_XXXX/text.txt
data/extracted/pymupdf_probe/page_XXXX/page_render.png
data/extracted/pymupdf_probe/page_XXXX/embedded_image_XX.*
data/extracted/pymupdf_probe/manifest.json
```

Purpose: extract raw page text, render each page, extract embedded images, and create a manifest for validation and skipped-page checks.

### 2. Parse product records

```bash
python -m rs_demo parse-products
```

Output:

```text
data/extracted/product_parse_sample.jsonl
```

Current full-PDF result:

```text
533 product records
360 pages with parsed products
```

Expected skipped page ranges:

```text
1-9, 62-63, 150-151, 204-205, 332-333, 372-373, 380-386
```

These are front matter, tour/map pages, indexes, acknowledgments, or credits.

### 3. Crop product images

```bash
python -m rs_demo crop-images
```

Outputs:

```text
data/extracted/product_image_crops/
data/extracted/product_image_crops_manifest.json
```

This also updates `data/extracted/product_parse_sample.jsonl` with:

```text
cropped_product_image_path
```

The cropper is approximate. It removes large blank regions by finding the largest non-white connected component in each embedded image.

### 4. Generate validation report

```bash
python -m rs_demo validate-catalogue
```

Output:

```text
data/extracted/catalogue_validation_report.md
```

Use this report to inspect medium-confidence records, missing ABV/country, rare styles, suspicious names, skipped page ranges, and multi-product pages.

### 5. Generate product Markdown for manual review

```bash
python -m rs_demo export-markdown
```

Outputs:

```text
data/extracted/product_markdown/index.md
data/extracted/product_markdown/pXXXX-product-id.md
```

Start manual review from `data/extracted/product_markdown/index.md`. Each product Markdown file contains structured fields, descriptions, brand text, cropped and original images, full page render, and raw parsed block.

### 6. Generate mock product embeddings

```bash
python -m rs_demo build-mock-embeddings
```

Outputs:

```text
data/embeddings/mock/metadata.jsonl
data/embeddings/mock/text_embeddings.npy
data/embeddings/mock/image_embeddings.npy
data/embeddings/mock/multimodal_embeddings.npy
data/embeddings/mock/manifest.json
```

The mock model is deterministic and local. It writes three aligned NumPy arrays: product text only, product image only, and multimodal (text + image evidence). Use this stage to test loading, ranking, and evaluation code without a remote embedding API.

### 7. Generate mock query embeddings

```bash
python -m rs_demo build-mock-query-embeddings
```

Inputs:

```text
data/eval/text_queries.jsonl
data/eval/image_queries.jsonl
data/eval/image_text_queries.jsonl
data/eval/cropped_image_text_queries.jsonl
```

Outputs:

```text
data/embeddings/mock/queries/text/
data/embeddings/mock/queries/image/
data/embeddings/mock/queries/image_text/
data/embeddings/mock/queries/cropped_image_text/
```

The query modes are intentionally separate:

- text only;
- image only, including cropped bottle and whole scene images;
- whole scene plus the question “What is the whisky in this image?”;
- cropped bottle plus the same question.

### 8. Run mock retrieval evaluation

```bash
python -m rs_demo run-mock-evaluation
```

Output:

```text
data/eval/mock_retrieval_report.json
```

This ranks products with cosine similarity and reports `hit@1`, `hit@5`, `hit@10`, and `MRR`. The current mock model is hash-based, so these scores are only a pipeline sanity check, not evidence of real retrieval quality.

### 9. Generate Gemini product embeddings

Real embedding CLI runs require `GOOGLE_API_KEY` or `GEMINI_API_KEY` in your shell environment
or local uncommitted `.env`. The code writes separate product arrays for text, image, and
multimodal product representations:

```bash
python -m rs_demo build-gemini-embeddings --mode text --sleep-seconds 0.8
python -m rs_demo build-gemini-embeddings --mode image --sleep-seconds 0.8
python -m rs_demo build-gemini-embeddings --mode multimodal --sleep-seconds 0.8
```

Outputs:

```text
data/embeddings/gemini/metadata.jsonl
data/embeddings/gemini/text_embeddings.npy
data/embeddings/gemini/image_embeddings.npy
data/embeddings/gemini/multimodal_embeddings.npy
data/embeddings/gemini/manifest.json
```

The product metadata order is shared by all three arrays. The pipeline fails if existing arrays do not match the current product order, unless `--force` is used.

### 10. Generate Gemini query embeddings

```bash
python -m rs_demo build-gemini-query-embeddings --mode text --sleep-seconds 0.8
python -m rs_demo build-gemini-query-embeddings --mode image --sleep-seconds 0.8
python -m rs_demo build-gemini-query-embeddings --mode image_text --sleep-seconds 0.8
python -m rs_demo build-gemini-query-embeddings --mode cropped_image_text --sleep-seconds 0.8
```

Outputs:

```text
data/embeddings/gemini/queries/text/
data/embeddings/gemini/queries/image/
data/embeddings/gemini/queries/image_text/
data/embeddings/gemini/queries/cropped_image_text/
```

Use `--limit-queries` and `--max-requests` for quota-controlled dry runs. The query loader validates required text/image fields and image file existence before making API calls.

### 11. Run Gemini retrieval evaluation

```bash
python -m rs_demo run-gemini-evaluation --mode text
python -m rs_demo run-gemini-evaluation --mode image
python -m rs_demo run-gemini-evaluation --mode image_text
python -m rs_demo run-gemini-evaluation --mode cropped_image_text_to_image
python -m rs_demo run-gemini-evaluation --mode cropped_image_text_to_multimodal
```

Output:

```text
data/eval/gemini_retrieval_report.json
```

The report includes these retrieval settings:

```text
text                                  text query -> product text
text_to_multimodal                    text query -> product multimodal
image                                 image query -> product image
image_to_multimodal                   image query -> product multimodal
image_text                            whole image + text query -> product multimodal
cropped_image_text_to_image           cropped image + text query -> product image
cropped_image_text_to_multimodal      cropped image + text query -> product multimodal
```

The `image` and `image_to_multimodal` sections each contain both cropped-bottle and whole-scene image queries; the review notebooks split them for easier inspection.

### 12. Run the managed RAG text baseline

The first managed RAG comparison is:

```text
text query -> Google File Search product text store -> generated top-k product IDs
```

It is comparable to the local `text query -> product text embeddings` experiment, but it is not a raw-vector comparison. File Search handles retrieval internally, then Gemini generates a JSON ranking from the retrieved catalogue context.

Build the product text corpus locally:

```bash
python -m rs_demo build-rag-text-corpus
```

Outputs:

```text
data/rag/product_text_corpus/*.txt
data/rag/product_text_corpus/manifest.jsonl
```

Create and populate the File Search store:

```bash
python -m rs_demo create-rag-text-store --sleep-seconds 0.8 --no-wait
```

Output:

```text
data/rag/rag_product_text_store.json
```

This step uses the Google API and indexes the product documents with `models/gemini-embedding-2`. It is the billable step. Use `--limit-products` for a small smoke test before uploading the full catalogue.

The ingestion command writes its manifest incrementally and can resume from an existing manifest. For larger stores, use bounded concurrency:

```bash
python -m rs_demo create-rag-text-store \
  --sleep-seconds 0.2 \
  --concurrency 5 \
  --progress-every 25 \
  --no-wait
```

Run the text-query RAG evaluation:

```bash
python -m rs_demo run-rag-text-evaluation --top-k 5
```

Output:

```text
data/eval/gemini_rag_text_report.json
```

The report includes the same retrieval metrics (`hit@1`, `hit@5`, `MRR`) plus RAG diagnostics such as invalid generated product IDs.

### 13. Prepare the managed RAG multimodal corpus

Build one compact PDF product sheet per product. Each PDF contains product metadata, description text, brand context, and the cropped bottle image embedded directly in the file:

```bash
python -m rs_demo build-rag-multimodal-corpus
```

Outputs:

```text
data/rag/product_multimodal_corpus/*.pdf
data/rag/product_multimodal_corpus/manifest.jsonl
```

Current generated size:

```text
533 product PDFs
about 23 MB total
```

Create a separate File Search store for these multimodal product sheets:

```bash
python -m rs_demo create-rag-multimodal-store \
  --concurrency 5 \
  --progress-every 25 \
  --no-wait
```

This must be a new store, for example:

```text
rag_product_multimodal_store
```

Do not reuse `rag_product_text_store`, because File Search store contents persist until deleted and the experiment needs separate text-only and multimodal baselines.

Run all query sets against the multimodal File Search store:

```bash
python -m rs_demo run-rag-evaluation \
  --store-manifest data/rag/rag_product_multimodal_store.json \
  --queries data/eval/text_queries.jsonl \
  --out data/eval/gemini_rag_multimodal_text_report.json \
  --report-key rag_multimodal_text \
  --model gemini-3.1-flash-lite \
  --sleep-seconds 5

python -m rs_demo run-rag-evaluation \
  --store-manifest data/rag/rag_product_multimodal_store.json \
  --queries data/eval/image_queries.jsonl \
  --out data/eval/gemini_rag_multimodal_image_report.json \
  --report-key rag_multimodal_image \
  --model gemini-3.1-flash-lite \
  --sleep-seconds 5 \
  --continue-on-error

python -m rs_demo run-rag-evaluation \
  --store-manifest data/rag/rag_product_multimodal_store.json \
  --queries data/eval/image_text_queries.jsonl \
  --out data/eval/gemini_rag_multimodal_image_text_report.json \
  --report-key rag_multimodal_image_text \
  --model gemini-3.1-flash-lite \
  --sleep-seconds 5 \
  --continue-on-error

python -m rs_demo run-rag-evaluation \
  --store-manifest data/rag/rag_product_multimodal_store.json \
  --queries data/eval/cropped_image_text_queries.jsonl \
  --out data/eval/gemini_rag_multimodal_cropped_image_text_report.json \
  --report-key rag_multimodal_cropped_image_text \
  --model gemini-3.1-flash-lite \
  --sleep-seconds 5 \
  --continue-on-error
```

The combined manual-review summary is:

```text
data/eval/gemini_rag_multimodal_query_summary.md
```

### 14. Run the managed RAG image-store baseline

The image-store RAG comparison mirrors the local product-image embedding experiments:

```text
image query -> Google File Search product image store -> generated top-k product IDs
image + text query -> Google File Search product image store -> generated top-k product IDs
```

Build one compressed JPEG product image per product:

```bash
python -m rs_demo build-rag-image-corpus
```

Outputs:

```text
data/rag/product_image_corpus/*.jpg
data/rag/product_image_corpus/manifest.jsonl
```

Create a separate File Search store for the product image corpus:

```bash
python -m rs_demo create-rag-image-store \
  --concurrency 5 \
  --progress-every 25
```

The upload manifest is resumable. If transient network failures occur, rerun the same command; completed uploads are skipped and incomplete records are retried.

Run the three image-store query settings:

```bash
python -m rs_demo run-rag-evaluation \
  --store-manifest data/rag/rag_product_image_store.json \
  --queries data/eval/image_queries.jsonl \
  --out data/eval/gemini_rag_image_image_report.json \
  --report-key rag_image_image \
  --model gemini-3.1-flash-lite \
  --sleep-seconds 5 \
  --continue-on-error

python -m rs_demo run-rag-evaluation \
  --store-manifest data/rag/rag_product_image_store.json \
  --queries data/eval/image_text_queries.jsonl \
  --out data/eval/gemini_rag_image_image_text_report.json \
  --report-key rag_image_image_text \
  --model gemini-3.1-flash-lite \
  --sleep-seconds 5 \
  --continue-on-error

python -m rs_demo run-rag-evaluation \
  --store-manifest data/rag/rag_product_image_store.json \
  --queries data/eval/cropped_image_text_queries.jsonl \
  --out data/eval/gemini_rag_image_cropped_image_text_report.json \
  --report-key rag_image_cropped_image_text \
  --model gemini-3.1-flash-lite \
  --sleep-seconds 5 \
  --continue-on-error
```

The combined manual-review summary is:

```text
data/eval/gemini_rag_image_query_summary.md
```

---

## Common development loop

When fixing parser behavior:

```bash
python -m rs_demo parse-products
python -m rs_demo crop-images
python -m rs_demo validate-catalogue
python -m rs_demo export-markdown
python -m rs_demo build-mock-embeddings
python -m rs_demo build-mock-query-embeddings
python -m rs_demo run-mock-evaluation
pytest -q
ruff check .
```

If the parser change only affects text fields and not image paths, the crop step can be skipped temporarily. Run it again before treating generated Markdown as final for review.

---

## Review outputs

For manual catalogue review:

```text
data/extracted/product_markdown/index.md
data/extracted/catalogue_validation_report.md
```

For retrieval review:

```text
data/eval/gemini_retrieval_report.json
notebooks/gemini_review_01_text_to_product_text.ipynb
notebooks/gemini_review_02_text_to_product_multimodal.ipynb
notebooks/gemini_review_03_cropped_image_to_product_image.ipynb
notebooks/gemini_review_04_whole_image_to_product_image.ipynb
notebooks/gemini_review_05_cropped_image_to_product_multimodal.ipynb
notebooks/gemini_review_06_whole_image_to_product_multimodal.ipynb
notebooks/gemini_review_07_image_text_to_product_multimodal.ipynb
notebooks/gemini_review_08_cropped_image_text_to_product_image.ipynb
notebooks/gemini_review_09_cropped_image_text_to_product_multimodal.ipynb
```

These notebooks load local embeddings and reports only. They do not make API calls.

For live demos that do make API calls from keys typed into notebook cells, use:

```text
notebooks/demo_01_direct_embedding_results.ipynb
notebooks/demo_02_rag_results.ipynb
```
