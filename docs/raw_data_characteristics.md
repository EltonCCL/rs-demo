# Raw Data Characteristics

This document records what we have learned from the professor-provided whisky PDF so far.
Use it as a reminder before changing the parser, embedding pipeline, or product schema.

## Source

- Primary file: `data/raw/Great Whiskeys.pdf`
- Current extraction tool: PyMuPDF
- Probe output: `data/extracted/pymupdf_probe/`
- Parsed sample output: `data/extracted/product_parse_sample.jsonl`

## What PyMuPDF Gives Us

PyMuPDF can extract three useful artifacts:

- raw page text, saved as `page_XXXX/text.txt`;
- rendered page images, saved as `page_XXXX/page_render.png`;
- embedded page images, usually saved as `page_XXXX/embedded_image_01.jpeg`.

For product pages, text extraction is generally usable. Page rendering also works. Embedded
images are often useful bottle/page images, but they are not guaranteed to map cleanly to every
product on the page.

## Page Structure

Most product pages follow this rough structure:

```text
page number
section letter
side/header noise
brand or distillery heading
country / location / website / owner metadata
brand or distillery background paragraph
product name
style / region / ABV
product tasting description
next product name
style / region / ABV
product tasting description
```

Repeated page noise includes:

```text
W H I S K E Y S
G R E A T
single section letters such as A
page numbers
direction arrows such as ▶ and ◀
```

## Atomic Product Unit

The recommendation unit should be one whisky expression, not one page.

One page can contain multiple product records. For example, page 21 contains:

- `ARDBEG 10-YEAR-OLD`
- `ARDBEG AIRIGH NAM BEIST`

Page 22 continues the same brand and contains:

- `ARDBEG BLASDA`
- `ARDBEG UIGEADAIL`

These four records belong to the same brand/distillery, `ARDBEG`.

## Brand Description Behavior

Brand or distillery descriptions may span multiple pages.

Important example:

- Page 21 starts the `ARDBEG` background.
- Page 22 continues the `ARDBEG` background.
- The four Ardbeg product records across pages 21 and 22 should share one combined
  `brand_description`.

Continuation pages may omit metadata such as country, location, or website. In the Ardbeg case,
page 22 does not repeat `Scotland` or `www.ardbeg.com`, so those values should be inherited from
page 21 when records are grouped by brand.

## Product Block Pattern

Product blocks are usually detected by:

- uppercase product name lines;
- followed by a style/specification line;
- followed by a tasting description.

Examples of style/specification lines:

```text
SINGLE MALT: ISLAY 46% ABV
SINGLE MALT: SPEYSIDE
40% ABV
BLEND 40% ABV
CANADIAN RYE 40% ABV
BOURBON 50% ABV
```

The style/specification line can be split across multiple lines, especially when `ABV` appears
on a separate line.

## Known Text Issues

The PDF text is not perfectly clean.

Known issues:

- ligatures may appear, such as `ﬁ`, and should be normalized to `fi`;
- line wrapping can split words, such as `medium-` + `bodied`;
- page text can contain OCR-like errors, such as `100 PIPERS` appearing as `1OO PIPERS`;
- product names may contain words that also look like style labels, such as
  `AMRUT PEATED INDIAN SINGLE MALT`;
- prose may contain style-like phrases, such as `Rye Whiskey`, that should not create a fake
  product record.

## Image Association

Many product pages have one embedded image. This does not always mean every product on the page
has a high-confidence product image.

Current heuristic:

- one product on page: image confidence `high`;
- multiple products on page, first product: image confidence `medium`;
- multiple products on page, later products: image confidence `low`;
- no embedded image: image confidence `none`.

This is only a prototype heuristic. For recommendation, image evidence should be treated as weak
unless the image-product relationship is visually confirmed.

## Parser Regression Pages

Current tests cover these representative cases:

- Page 14: avoids false product split from prose containing `Rye Whiskey`;
- Page 15: handles multiline brand heading `AMERICAN SPIRIT`;
- Page 16: handles product names containing `SINGLE MALT`;
- Page 21: parses two Ardbeg products;
- Page 22: handles Ardbeg continuation page;
- Page 24: parses single Armorik product;
- Pages 21 and 22 together: combines shared Ardbeg brand description.

## Current Implication

PyMuPDF is good enough for the first extraction prototype, but the main challenge is not raw
extraction. The main challenge is turning noisy page text into reliable product-level records
with correct shared brand metadata, product descriptions, and image confidence labels.

## Full Extraction Pass

We ran PyMuPDF across the full PDF, not just the first 25 pages.

Current full-pass outputs:

- PDF pages extracted: 386
- candidate product records parsed: 533
- pages with at least one parsed product record: 360
- parsed output: `data/extracted/product_parse_sample.jsonl`
- extraction manifest: `data/extracted/pymupdf_probe/manifest.json`

The count is plausible because the book is titled around 500 whiskeys, but it should not yet be
treated as fully validated catalogue data.

## Non-Product Page Types

Some pages are intentionally not product pages and should not create product records.

Observed examples:

| PDF pages | Type | Notes |
|---|---|---|
| 1-9 | front matter / contents / introduction | no product records expected |
| 62-63 | Whisky Tour: Islay | tour text, map labels, and distillery locations |
| 150-151 | Whisky Tour: Speyside | tour/map content |
| 204-205 | Whiskey Tour: Ireland | tour/map content |
| 332-333 | Whiskey Tour: Japan | tour/map content |
| 372-373 | Whiskey Tour: Kentucky | tour/map content |
| 380-386 | indexes, acknowledgments, credits | index entries and publication credits |

The current heuristic parser naturally skips most of these because they do not match the product
block pattern. This is useful, but we should make page classification explicit before building the
final catalogue.

## Current Full-Pass Quality Signals

Current parser summary:

- high-confidence records: 519
- medium-confidence records: 14
- records missing ABV: 14
- records missing country: 79

Image-confidence summary:

- high: 190
- medium: 170
- low: 173

Main style counts:

- Single Malt: 265
- Blend: 141
- Bourbon: 46
- Blended Malt: 15
- Rye Whiskey: 12

After the first full pass, several real product pages were missed because their style labels were
outside the initial parser vocabulary. We added coverage for labels such as:

- `SINGLE GRAIN`
- `IRISH POT STILL WHISKEY`
- `PURE POT STILL`
- `NEW MAKE`
- `POTEEN`
- `MALT`
- `KENTUCKY WHISKEY`
- `OREGON WHISKEY`
- `COLORADO WHISKEY`
- `MIXED GRAIN WHISKEY`
- `BLENDED CANADIAN RYE`

These counts are useful smoke tests, not final evaluation metrics.

## Manual Review Artifacts

We generate two review artifacts after parsing:

- `data/extracted/catalogue_validation_report.md`
- `data/extracted/product_markdown/index.md`

The validation report summarizes catalogue-level risks, including skipped pages, missing ABV,
missing country, rare styles, suspicious names, and medium-confidence records.

The product Markdown directory contains one file per parsed product. Each product file includes:

- structured fields;
- product description;
- shared brand description;
- cropped product image link;
- original embedded/product image link;
- full page render link;
- raw parsed text block.

Use `data/extracted/product_markdown/index.md` as the starting point for manual checks.

## Product Image Cropping

The raw embedded images often contain the bottle plus unnecessary whitespace or layout marks.
We generate rough crops with:

```bash
python -m rs_demo crop-images
```

The cropper finds the largest non-white connected component in each embedded image, adds padding,
and writes cropped PNGs under:

```text
data/extracted/product_image_crops/
```

It also writes:

```text
data/extracted/product_image_crops_manifest.json
```

and adds `cropped_product_image_path` to `data/extracted/product_parse_sample.jsonl`.

This is intentionally approximate. It is meant to make manual review and image embeddings cleaner,
not to produce publication-quality bottle cutouts.

## Known Full-Pass Issues

The full pass exposed several parser issues to revisit:

- OCR-like text remains, for example `100 PIPERS` may appear as `1OO PIPERS`.
- Some page header noise can leak into product names, for example a `W H I S K I E S` prefix.
- Variable-ABV products may produce awkward style values such as `Bourbon (Variable Abv)`.
- Some styles/ranges are not normalized yet, for example `Blended Malt Range`.
- Country can be missing on continuation pages unless inherited from same-brand records.
- Index and tour pages are currently skipped by pattern behavior, but should eventually be
  excluded by an explicit page classifier.

Before embeddings, we should add a validation stage that samples records from early, middle, late,
tour-adjacent, and index-adjacent pages.
