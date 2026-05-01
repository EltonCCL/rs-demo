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
```

Embeddings are intentionally not implemented yet. We first want a clean enough product catalogue.

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

## Full Pipeline

Run these commands from the repo root.

### 1. Extract Page Text And Images

```bash
python scripts/probe_pdf_extraction.py data/raw/Great\ Whiskeys.pdf --max-pages 1000
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
python scripts/prototype_product_parser.py
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
python scripts/crop_product_images.py
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
python scripts/validate_catalogue.py
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
python scripts/export_product_markdown.py
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

## Common Development Loop

When fixing parser behavior:

```bash
python scripts/prototype_product_parser.py
python scripts/crop_product_images.py
python scripts/validate_catalogue.py
python scripts/export_product_markdown.py
pytest -q
ruff check .
```

If the parser change only affects text fields and not image paths, the crop step can be skipped
temporarily. Run it again before treating generated Markdown as final for review.

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

After manual validation, create embedding input files:

```text
data/catalogue/whisky_products.jsonl
data/catalogue/embedding_inputs.jsonl
```

The embedding design should keep product text, brand context, and image evidence separate at
first, then combine scores during retrieval/ranking.
