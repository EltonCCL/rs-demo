

# Whisky Recommendation Demo: Goal, Scope, and Work Plan

## 1. Goal

Build a small, rigorous, demo-ready whisky recommendation system that supports three user query types:

1. text query,
2. image query,
3. text + image query.

The system should return a ranked list of whisky products, not PDF pages, wiki pages, distilleries, regions, or concepts.

The core research idea is:

> Gemini Embedding 2 can support multimodal retrieval, but retrieval alone is not a recommender system. A useful recommender must operate over product-level whisky records and rank candidates according to the user's expressed intent, constraints, and available product evidence.

## 2. Current Decision

We discard the LLM Wiki direction for this stage.

Reason:

- LLM Wiki organizes knowledge into concept-level pages.
- Our recommendation system needs product-level candidates.
- The final output should be ranked whisky products or whisky expressions.

Therefore, the main artifact should be a structured whisky catalogue where each row is one recommendable whisky expression.

## 3. Core Use Case

A user wants whisky recommendations but may express the request in different forms.

Examples:

```text
Text query:
I want a smoky but beginner-friendly Islay whisky.

Image query:
User uploads a bottle photo or a PDF page crop.

Text + image query:
User uploads a whisky bottle image and says:
Something like this, but sweeter and less smoky.
```

The system should always return:

```text
ranked whisky products + explanation + known limitations
```

## 4. Problem Definition

We define the task as multimodal whisky recommendation.

Given:

- a user query `q`, which may be text, image, or text + image;
- a whisky catalogue `I`, where each item is a whisky product/expression;

return a ranked list of whisky products that best match the user's expressed taste, visual reference, occasion, or practical constraints.

The task is not simply to retrieve the nearest PDF page. The task is to recommend whisky products.

## 5. Atomic Recommendation Unit

The atomic unit must be:

```text
one whisky expression / product
```

not:

```text
one PDF page
one brand
one distillery
one region
one concept page
```

This matters because one PDF page may contain multiple whisky expressions. For example, a page may describe both:

```text
Suntory Hibiki 17-Year-Old
Suntory Hibiki 30-Year-Old
```

In this case, the system should create two product records, not one page-level record.

## 6. Data Sources

### 6.1 Primary Source

The professor-provided whisky PDF is the primary source.

Expected use:

- extract whisky product names;
- extract descriptions and tasting notes;
- extract structured metadata when available;
- render page images;
- optionally crop bottle images when reliable;
- track source page number for traceability.

### 6.2 Optional Source

Whiskybase may be used for limited enrichment, such as:

- rating;
- number of votes;
- popularity signal;
- additional product metadata.

Important constraint:

> Do not assume unrestricted large-scale scraping from Whiskybase. Use it carefully, for manual lookup, small-scale enrichment where permitted, or as motivation for what rating signals would be useful.

## 7. Product Record Schema

Each extracted whisky product should become a structured record.

Expected fields:

```json
{
  "product_id": "string",
  "name": "string",
  "brand_or_distillery": "string | null",
  "country": "string | null",
  "region": "string | null",
  "style": "string | null",
  "age": "number | null",
  "abv": "number | null",
  "description": "string",
  "tasting_notes": "string | null",
  "source_page": "number",
  "page_image_path": "string | null",
  "product_image_path": "string | null",
  "image_confidence": "high | medium | low | none",
  "whiskybase_rating": "number | null",
  "whiskybase_num_votes": "number | null"
}
```

## 8. Image Association Edge Cases

Because one page may include multiple products, image association must be handled carefully.

Rules:

| Case | Handling |
|---|---|
| One page has one product and one bottle image | Assign image to product with high confidence |
| One page has multiple products and one image clearly belongs to one product | Assign image to that product; mark others as lower confidence or page-context only |
| One page has multiple products and image-product relation is unclear | Attach full page image as weak visual context and set image confidence to low |
| No usable image | Use text-only representation |

We should not pretend that a page image always belongs to every product on that page.

## 9. Supported Query Types

The final demo should support three query modes.

### 9.1 Text Query

Input:

```text
I want a smoky but beginner-friendly Islay whisky.
```

Main signal:

- semantic match between user text and whisky text profile.

### 9.2 Image Query

Input:

```text
uploaded bottle photo, label image, or PDF page crop
```

Main signal:

- visual match between query image and product/page image evidence.

Expected behavior:

- identify visually similar or related whisky products;
- return ranked product candidates;
- explain that image evidence may identify bottle/brand/page but may not fully determine taste.

### 9.3 Text + Image Query

Input:

```text
uploaded image + natural-language modifier
```

Example:

```text
Something like this, but sweeter and less smoky.
```

Main signals:

- image reference matching;
- text-based taste or constraint matching;
- final recommendation ranking.

## 10. System Architecture

The architecture should separate extraction, representation, retrieval, and ranking.

```text
Professor whisky PDF
        ↓
Render pages and extract text
        ↓
Extract product-level whisky records
        ↓
Create product catalogue
        ↓
Build embeddings
    - product text embedding
    - page/product image embedding
    - optional multimodal embedding
        ↓
User query: text / image / text+image
        ↓
Candidate retrieval
        ↓
Recommendation ranking
        ↓
Ranked whisky products + explanation
```

## 11. Approaches to Compare

We should compare multiple methods so the project is not just a single demo.

### 11.1 Keyword Baseline

Use lexical matching over product text.

Purpose:

- simple baseline;
- shows limitations of exact keyword matching.

### 11.2 Text Embedding Retrieval

Use vector embeddings over product descriptions and tasting notes.

Purpose:

- tests whether embeddings improve semantic taste matching.

### 11.3 Image Embedding Retrieval

Use image embeddings over page images or bottle crops.

Purpose:

- supports image-based whisky discovery;
- demonstrates multimodal capability.

### 11.4 Text + Image Retrieval

Use text and image together through either:

- a combined multimodal embedding, or
- separate text/image embeddings with score fusion.

Purpose:

- supports queries like “something like this, but sweeter.”

### 11.5 Recommendation Ranking

Use retrieval results plus product-level evidence.

Possible ranking signals:

- text semantic match;
- image similarity;
- constraint satisfaction;
- optional Whiskybase rating or popularity;
- confidence in extracted information.

Purpose:

- turns retrieval into recommendation.

## 12. Expected Demo

The demo should show:

1. a text-only query;
2. an image-only query;
3. a text + image query;
4. ranked whisky products;
5. short explanations;
6. limitations or missing evidence.

Example output:

```text
Query:
I want a smoky but beginner-friendly Islay whisky.

Recommendation 1:
Whisky name
Reason: tasting notes mention peat, smoke, citrus, and gentle sweetness.
Limitation: price is not available in the PDF.

Recommendation 2:
Whisky name
Reason: same region and similar smoky profile.
Limitation: beginner-friendliness is inferred, not explicitly stated.
```

## 13. What We Need To Do

### Step 1: Inspect the PDF structure

Tasks:

- confirm page layout patterns;
- identify how many products may appear per page;
- check whether product text is extractable;
- check whether images are embedded or need page rendering/cropping.

Expected output:

```text
PDF structure notes
sample pages
known edge cases
```

### Step 2: Build extraction prototype

Tasks:

- render pages to images;
- extract page text;
- split page text into product-level records;
- keep source page numbers;
- manually validate a small sample.

Potential tools:

- PyMuPDF for PDF text extraction and page rendering;
- Marker or Surya only if PyMuPDF is not enough.

Expected output:

```text
sample whisky_profiles.jsonl
sample page images
manual validation notes
```

### Step 3: Define product schema and validation rules

Tasks:

- finalize record fields;
- define required vs optional fields;
- define image confidence rules;
- define how to handle missing ABV, age, region, or image.

Expected output:

```text
schema document
validation checklist
```

### Step 4: Build embedding index

Tasks:

- create text profile for each whisky product;
- embed product text;
- embed page/product images where available;
- store embeddings and metadata;
- build nearest-neighbor search.

Expected output:

```text
text embeddings
image embeddings
local vector index
```

### Step 5: Implement query modes

Tasks:

- text query retrieval;
- image query retrieval;
- text + image query retrieval;
- normalize returned candidates into product-level results.

Expected output:

```text
three working query modes
ranked product outputs
```

### Step 6: Add recommendation ranking

Tasks:

- combine retrieval signals with metadata;
- add simple constraint handling;
- optionally add Whiskybase rating enrichment;
- add explanation generation grounded in product fields.

Expected output:

```text
ranked recommendations
explanations
failure cases
```

### Step 7: Prepare demo and slides

Tasks:

- show three query modes;
- compare keyword, embedding, and recommendation ranking;
- show where image helps;
- show limitations;
- explain future improvements.

Expected output:

```text
working demo
slide-ready examples
limitations and future work
```

## 14. Success Criteria

The project is successful if we can show:

- product-level whisky recommendations;
- support for text, image, and text+image queries;
- embeddings used for candidate retrieval;
- recommendation ranking beyond pure similarity search;
- explanations grounded in product text, metadata, or image evidence;
- honest limitations for missing data, ambiguous images, and uncertain extraction;
- a demo that is understandable within a short presentation.

## 15. Key Risks

| Risk | Why it matters | Mitigation |
|---|---|---|
| PDF page contains multiple products | Page-level retrieval may not equal product recommendation | Extract product-level records |
| Product image does not clearly match one expression | Image evidence may be misleading | Use image confidence labels |
| Text extraction order is messy | Product descriptions may be corrupted | Validate sample pages; use layout tools if needed |
| Whiskybase access is limited | Rating enrichment may not scale | Treat rating as optional |
| Image search identifies bottle but not taste | Visual match is not full recommendation | Combine image retrieval with text/metadata ranking |
| Embedding retrieval becomes only search | Weak recommender framing | Add ranking, constraints, and explanations |

## 16. Current Working Thesis

The working thesis is:

> A whisky recommender should operate over product-level whisky expressions rather than PDF pages or wiki concepts. Gemini Embedding 2 can support text, image, and text+image queries, making it suitable for multimodal candidate retrieval. However, retrieval alone is not recommendation. A useful system must construct product-level records, handle edge cases such as multiple products per page, and rank candidates using text evidence, visual evidence, metadata, optional rating signals, and grounded explanations.