# Pipeline and tooling

Step-by-step CLI flow from the PDF through mock embeddings and retrieval evaluation. Run commands from the repository root unless noted.

For **evaluation benchmark queries** (text, image, expected positives) and **links to the seven Gemini ranking notebooks** (`notebooks/gemini_review_*.ipynb`), see [evaluation_queries_and_labels.md](evaluation_queries_and_labels.md). For **PDF layout and parser context**, see [raw_data_characteristics.md](raw_data_characteristics.md).

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

### 6. Generate mock embeddings

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
```

Outputs:

```text
data/embeddings/mock/queries/text/
data/embeddings/mock/queries/image/
data/embeddings/mock/queries/image_text/
```

The three query modes are intentionally separate: text only; image only (crop or scene); whole scene plus the question “What is the whisky in this image?” for image+text.

### 8. Run mock retrieval evaluation

```bash
python -m rs_demo run-mock-evaluation
```

Output:

```text
data/eval/mock_retrieval_report.json
```

This ranks products with cosine similarity and reports `hit@1`, `hit@5`, `hit@10`, and `MRR`. The current mock model is hash-based, so these scores are only a pipeline sanity check, not evidence of real retrieval quality.

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

## Next planned stage

After the mock embedding pipeline is stable, replace the mock model with real embedding providers while keeping the same output contract:

```text
metadata.jsonl
text_embeddings.npy
image_embeddings.npy
multimodal_embeddings.npy
```

That enables comparing text-only, image-only, late-fusion, and native multimodal retrieval on the same product records.
