# Whisky Recommendation Demo

Small research/demo codebase for building a product-level whisky recommendation system from a
PDF source. The current checkpoint focuses on extraction, product parsing, image preparation, and
manual validation before embeddings.

## Current Goal

Build a whisky catalogue where each row is one recommendable whisky expression, not one PDF page.

Supported target query modes later:

- text query;
- image query;
- text + image query.

Current stage:

```text
PDF -> page text/images -> product records -> validation report -> manual review Markdown
    -> mock product/query embeddings -> mock retrieval evaluation
```

The current embedding step uses a deterministic mock model. It is only for testing the data flow,
array storage, and later retrieval code before connecting a real embedding provider.

## Setup

This repo uses conda only to create the Python environment. Python packages are installed with
pip, not conda.

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

Run tests and lint:

```bash
pytest -q
ruff check .
```

## Input Data

Expected PDF location:

```text
data/raw/Great Whiskeys.pdf
```

The raw PDF is not committed by default. `data/raw/.gitkeep` only keeps the directory present.

## Code Organization

Reusable pipeline code lives in the package under:

```text
src/rs_demo/
```

The codebase is organized as a library first. Command-line access is exposed through the package
CLI:

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

This keeps the code easier to test and lets later retrieval/evaluation code call the same pipeline
directly as Python classes.

## Full Pipeline

Run these commands from the repo root.

### 1. Extract Page Text And Images

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

Purpose:

- extract raw page text;
- render each page;
- extract embedded images;
- create a manifest for validation and skipped-page checks.

### 2. Parse Product Records

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

### 3. Crop Product Images

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

The cropper is approximate. It removes large blank regions by finding the largest non-white
connected component in each embedded image.

### 4. Generate Validation Report

```bash
python -m rs_demo validate-catalogue
```

Output:

```text
data/extracted/catalogue_validation_report.md
```

Use this report to inspect:

- medium-confidence records;
- missing ABV;
- missing country;
- rare styles;
- suspicious names;
- skipped page ranges;
- multi-product pages.

### 5. Generate Product Markdown For Manual Review

```bash
python -m rs_demo export-markdown
```

Outputs:

```text
data/extracted/product_markdown/index.md
data/extracted/product_markdown/pXXXX-product-id.md
```

Start manual review from:

```text
data/extracted/product_markdown/index.md
```

Each product Markdown file contains:

- structured product fields;
- product description;
- shared brand/distillery description;
- cropped product image;
- original embedded image;
- full page render;
- raw parsed block.

### 6. Generate Mock Embeddings

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

The mock model is deterministic and local. It writes three aligned NumPy arrays:

- `text_embeddings.npy`: product text only;
- `image_embeddings.npy`: product image path/content only;
- `multimodal_embeddings.npy`: product text and image evidence together.

Use this stage to test loading, ranking, and evaluation code without paying for or depending on a
remote embedding API.

### 7. Generate Mock Query Embeddings

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

The three query modes are intentionally separate:

- `text`: natural language only;
- `image`: cropped bottle image or whole scene image only;
- `image_text`: whole scene image plus the question `What is the whisky in this image?`.

### 8. Run Mock Retrieval Evaluation

```bash
python -m rs_demo run-mock-evaluation
```

Output:

```text
data/eval/mock_retrieval_report.json
```

This ranks products with cosine similarity and reports `hit@1`, `hit@5`, `hit@10`, and `MRR`.
The current mock model is hash-based, so these scores are only a pipeline sanity check. They are
not evidence of real retrieval quality.

## Common Development Loop

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

If the parser change only affects text fields and not image paths, the crop step can be skipped
temporarily. Run it again before treating generated Markdown as final for review.

## Evaluation Query Seed

The first evaluation seeds are:

```text
data/eval/text_queries.jsonl
data/eval/image_queries.jsonl
data/eval/image_text_queries.jsonl
```

Text queries contain:

- `query_id`;
- `query_type`;
- `query_style`;
- text `query`;
- `relevant_product_ids`;
- a `label_generation` note describing the rule-based keyword search used to select positives.

Image and image+text queries are built from the reviewed movie/TV scene image set:

```text
data/eval/movie_scene_query_images/
data/eval/movie_scene_bottle_crops/
```

For the main multimodal benchmark, image-only queries include both:

- manually cropped bottle images;
- whole movie/TV scene images.

Image+text queries use the whole scene image plus a natural identification question. These are not
final human relevance judgments. They are controlled seed labels so retrieval code can be tested
before calling a real embedding API.

## Important Design Notes

The parser is heuristic and specific to this PDF.

Important behaviors already handled:

- one PDF page can contain multiple product records;
- brand descriptions can span continuation pages;
- continuation product pages can inherit brand metadata from previous pages;
- rare style labels such as `POTEEN`, `NEW MAKE`, `SINGLE GRAIN`, and `PURE POT STILL` are parsed;
- trailing series/background prose can be moved from product description into brand description;
- image confidence is lower for later products on a multi-product page.

Known risks:

- OCR-like text errors remain, for example `100 PIPERS` may appear as `1OO PIPERS`;
- image-to-product association is still approximate;
- style normalization is not final;
- generated records need manual validation before embeddings.

More detailed extraction notes are in:

```text
docs/raw_data_characteristics.md
```

## Next Planned Stage

After the mock embedding pipeline is stable, replace the mock model with real embedding providers
while keeping the same output contract:

```text
metadata.jsonl
text_embeddings.npy
image_embeddings.npy
multimodal_embeddings.npy
```

This lets us compare text-only, image-only, late-fusion, and native multimodal retrieval using the
same product records.
