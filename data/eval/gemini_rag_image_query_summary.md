# Gemini RAG Product Image Store Query Summary

Store: `fileSearchStores/ragproductimagestore-dppy5hhkl8n5`

Documents: 533 product image files

## Overall Metrics

| Setting | Queries | Hit@1 | Hit@5 | MRR | Valid ID Rate | API Errors |
|---|---:|---:|---:|---:|---:|---:|
| Image -> image RAG store | 22 | 0.8182 | 0.8182 | 0.8182 | 1.0000 | 0 |
| Whole image + text -> image RAG store | 11 | 0.7273 | 0.7273 | 0.7273 | 1.0000 | 0 |
| Cropped image + text -> image RAG store | 11 | 0.8182 | 0.8182 | 0.8182 | 1.0000 | 0 |

## Hit@5 Misses

### Image -> image RAG store
- `iq004_crop` (cropped_bottle_identification): Blanton's Bourbon
  - returned: p0161-the-glenrothes-select-reserve, p0161-the-glenrothes-1975, p0108-dimple-12-year-old, p0108-dimple-15-year-old, p0173-guillon-no-1
- `iq004_scene` (whole_scene_identification): Blanton's Bourbon
  - returned: p0108-dimple-12-year-old, p0108-dimple-15-year-old, p0173-guillon-no-1, p0052-black-bottle, p0052-black-bottle-10-year-old
- `iq011_crop` (cropped_bottle_identification): Johnnie Walker Blue Label
  - returned: p0272-the-notch
- `iq011_scene` (whole_scene_identification): Johnnie Walker Blue Label
  - returned: p0148-glenfiddich-12-year-old, p0148-glenfiddich-15-year-old-solera-reserve, p0052-black-bottle, p0052-black-bottle-10-year-old, p0173-guillon-no-1

### Whole image + text -> image RAG store
- `itq004` (whole_scene_question): What is the whisky in this image?
  - returned: p0052-black-bottle
- `itq010` (whole_scene_question): What is the whisky in this image?
  - returned: p0052-black-bottle
- `itq011` (whole_scene_question): What is the whisky in this image?
  - returned: p0052-black-bottle, p0052-black-bottle-10-year-old, p0148-glenfiddich-12-year-old, p0148-glenfiddich-15-year-old-solera-reserve, p0173-guillon-no-1

### Cropped image + text -> image RAG store
- `citq004` (cropped_bottle_question): What is the whisky in this image?
  - returned: p0161-the-glenrothes-select-reserve, p0161-the-glenrothes-1975, p0108-dimple-12-year-old, p0108-dimple-15-year-old, p0173-guillon-no-1
- `citq011` (cropped_bottle_question): What is the whisky in this image?
  - returned: p0108-dimple-15-year-old

## Query Results

### Image -> image RAG store
| Query | Style | Hit@1 | Hit@5 | RR | Query / Reference | Top result | Returned IDs |
|---|---|---:|---:|---:|---|---|---|
| iq001_crop | cropped_bottle_identification | yes | yes | 1.0000 | Macallan 1962 Fine & Rare | p0244-the-macallan-30-year-old (The Macallan 30 Year Old) | p0244-the-macallan-30-year-old |
| iq001_scene | whole_scene_identification | yes | yes | 1.0000 | Macallan 1962 Fine & Rare | p0244-the-macallan-30-year-old (The Macallan 30 Year Old) | p0244-the-macallan-30-year-old |
| iq002_crop | cropped_bottle_identification | yes | yes | 1.0000 | Suntory Hibiki 17 | p0334-suntory-hibiki-17-year-old (Suntory Hibiki 17 Year Old) | p0334-suntory-hibiki-17-year-old |
| iq002_scene | whole_scene_identification | yes | yes | 1.0000 | Suntory Hibiki 17 | p0334-suntory-hibiki-17-year-old (Suntory Hibiki 17 Year Old) | p0334-suntory-hibiki-17-year-old |
| iq003_crop | cropped_bottle_identification | yes | yes | 1.0000 | Johnnie Walker Black Label | p0208-johnnie-walker-black-label (Johnnie Walker Black Label) | p0208-johnnie-walker-black-label |
| iq003_scene | whole_scene_identification | yes | yes | 1.0000 | Johnnie Walker Black Label | p0208-johnnie-walker-black-label (Johnnie Walker Black Label) | p0208-johnnie-walker-black-label |
| iq004_crop | cropped_bottle_identification | no | no | 0.0000 | Blanton's Bourbon | p0161-the-glenrothes-select-reserve (The Glenrothes Select Reserve) | p0161-the-glenrothes-select-reserve, p0161-the-glenrothes-1975, p0108-dimple-12-year-old, p0108-dimple-15-year-old, p0173-guillon-no-1 |
| iq004_scene | whole_scene_identification | no | no | 0.0000 | Blanton's Bourbon | p0108-dimple-12-year-old (Dimple 12 Year Old) | p0108-dimple-12-year-old, p0108-dimple-15-year-old, p0173-guillon-no-1, p0052-black-bottle, p0052-black-bottle-10-year-old |
| iq005_crop | cropped_bottle_identification | yes | yes | 1.0000 | Jack Daniel's Old No. 7 | p0199-jack-daniel-s-old-no-7 (Jack Daniel's Old No. 7) | p0199-jack-daniel-s-old-no-7, p0199-jack-daniel-s-single-barrel |
| iq005_scene | whole_scene_identification | yes | yes | 1.0000 | Jack Daniel's Old No. 7 | p0199-jack-daniel-s-old-no-7 (Jack Daniel's Old No. 7) | p0199-jack-daniel-s-old-no-7 |
| iq006_crop | cropped_bottle_identification | yes | yes | 1.0000 | Laphroaig | p0229-laphroaig-quarter-cask (Laphroaig Quarter Cask) | p0229-laphroaig-quarter-cask |
| iq006_scene | whole_scene_identification | yes | yes | 1.0000 | Laphroaig | p0229-laphroaig-quarter-cask (Laphroaig Quarter Cask) | p0229-laphroaig-quarter-cask |
| iq007_crop | cropped_bottle_identification | yes | yes | 1.0000 | Lagavulin | p0225-lagavulin-distillers-edition (Lagavulin Distillers Edition) | p0225-lagavulin-distillers-edition, p0225-lagavulin-21-year-old, p0224-lagavulin-16-year-old, p0224-lagavulin-12-year-old |
| iq007_scene | whole_scene_identification | yes | yes | 1.0000 | Lagavulin | p0224-lagavulin-16-year-old (Lagavulin 16 Year Old) | p0224-lagavulin-16-year-old |
| iq008_crop | cropped_bottle_identification | yes | yes | 1.0000 | Ardbeg 10 | p0021-ardbeg-10-year-old (Ardbeg 10 Year Old) | p0021-ardbeg-10-year-old |
| iq008_scene | whole_scene_identification | yes | yes | 1.0000 | Ardbeg 10 | p0021-ardbeg-10-year-old (Ardbeg 10 Year Old) | p0021-ardbeg-10-year-old |
| iq009_crop | cropped_bottle_identification | yes | yes | 1.0000 | Macallan 18 | p0244-the-macallan-30-year-old (The Macallan 30 Year Old) | p0244-the-macallan-30-year-old |
| iq009_scene | whole_scene_identification | yes | yes | 1.0000 | Macallan 18 | p0244-the-macallan-30-year-old (The Macallan 30 Year Old) | p0244-the-macallan-30-year-old |
| iq010_crop | cropped_bottle_identification | yes | yes | 1.0000 | Canadian Club | p0074-canadian-club-reserve (Canadian Club Reserve) | p0074-canadian-club-reserve, p0074-canadian-club-6-year-old-100-proof, p0075-canadian-club-premium, p0075-canadian-club-classic, p0376-windsor-canadian |
| iq010_scene | whole_scene_identification | yes | yes | 1.0000 | Canadian Club | p0075-canadian-club-premium (Canadian Club Premium) | p0075-canadian-club-premium, p0075-canadian-club-classic, p0074-canadian-club-reserve, p0074-canadian-club-6-year-old-100-proof, p0376-windsor-canadian |
| iq011_crop | cropped_bottle_identification | no | no | 0.0000 | Johnnie Walker Blue Label | p0272-the-notch (The Notch) | p0272-the-notch |
| iq011_scene | whole_scene_identification | no | no | 0.0000 | Johnnie Walker Blue Label | p0148-glenfiddich-12-year-old (Glenfiddich 12 Year Old) | p0148-glenfiddich-12-year-old, p0148-glenfiddich-15-year-old-solera-reserve, p0052-black-bottle, p0052-black-bottle-10-year-old, p0173-guillon-no-1 |

### Whole image + text -> image RAG store
| Query | Style | Hit@1 | Hit@5 | RR | Query / Reference | Top result | Returned IDs |
|---|---|---:|---:|---:|---|---|---|
| itq001 | whole_scene_question | yes | yes | 1.0000 | What is the whisky in this image? | p0244-the-macallan-30-year-old (The Macallan 30 Year Old) | p0244-the-macallan-30-year-old |
| itq002 | whole_scene_question | yes | yes | 1.0000 | What is the whisky in this image? | p0334-suntory-hibiki-17-year-old (Suntory Hibiki 17 Year Old) | p0334-suntory-hibiki-17-year-old |
| itq003 | whole_scene_question | yes | yes | 1.0000 | What is the whisky in this image? | p0208-johnnie-walker-black-label (Johnnie Walker Black Label) | p0208-johnnie-walker-black-label |
| itq004 | whole_scene_question | no | no | 0.0000 | What is the whisky in this image? | p0052-black-bottle (Black Bottle) | p0052-black-bottle |
| itq005 | whole_scene_question | yes | yes | 1.0000 | What is the whisky in this image? | p0199-jack-daniel-s-old-no-7 (Jack Daniel's Old No. 7) | p0199-jack-daniel-s-old-no-7, p0199-jack-daniel-s-single-barrel, p0128-george-dickel-no-12, p0128-george-dickel-barrel-select, p0113-early-times |
| itq006 | whole_scene_question | yes | yes | 1.0000 | What is the whisky in this image? | p0228-laphroaig10-year-old (Laphroaig 10 Year Old) | p0228-laphroaig10-year-old, p0228-laphroaig-10-year-old-cask-strength, p0229-laphroaig-quarter-cask, p0229-laphroaig-25-year-old, p0232-lauder-s |
| itq007 | whole_scene_question | yes | yes | 1.0000 | What is the whisky in this image? | p0224-lagavulin-16-year-old (Lagavulin 16 Year Old) | p0224-lagavulin-16-year-old |
| itq008 | whole_scene_question | yes | yes | 1.0000 | What is the whisky in this image? | p0021-ardbeg-10-year-old (Ardbeg 10 Year Old) | p0021-ardbeg-10-year-old, p0021-ardbeg-airigh-nam-beist, p0022-ardbeg-blasda, p0022-ardbeg-uigeadail, p0023-ardmore-traditional-cask |
| itq009 | whole_scene_question | yes | yes | 1.0000 | What is the whisky in this image? | p0244-the-macallan-30-year-old (The Macallan 30 Year Old) | p0244-the-macallan-30-year-old |
| itq010 | whole_scene_question | no | no | 0.0000 | What is the whisky in this image? | p0052-black-bottle (Black Bottle) | p0052-black-bottle |
| itq011 | whole_scene_question | no | no | 0.0000 | What is the whisky in this image? | p0052-black-bottle (Black Bottle) | p0052-black-bottle, p0052-black-bottle-10-year-old, p0148-glenfiddich-12-year-old, p0148-glenfiddich-15-year-old-solera-reserve, p0173-guillon-no-1 |

### Cropped image + text -> image RAG store
| Query | Style | Hit@1 | Hit@5 | RR | Query / Reference | Top result | Returned IDs |
|---|---|---:|---:|---:|---|---|---|
| citq001 | cropped_bottle_question | yes | yes | 1.0000 | What is the whisky in this image? | p0244-the-macallan-30-year-old (The Macallan 30 Year Old) | p0244-the-macallan-30-year-old |
| citq002 | cropped_bottle_question | yes | yes | 1.0000 | What is the whisky in this image? | p0334-suntory-hibiki-17-year-old (Suntory Hibiki 17 Year Old) | p0334-suntory-hibiki-17-year-old |
| citq003 | cropped_bottle_question | yes | yes | 1.0000 | What is the whisky in this image? | p0208-johnnie-walker-black-label (Johnnie Walker Black Label) | p0208-johnnie-walker-black-label |
| citq004 | cropped_bottle_question | no | no | 0.0000 | What is the whisky in this image? | p0161-the-glenrothes-select-reserve (The Glenrothes Select Reserve) | p0161-the-glenrothes-select-reserve, p0161-the-glenrothes-1975, p0108-dimple-12-year-old, p0108-dimple-15-year-old, p0173-guillon-no-1 |
| citq005 | cropped_bottle_question | yes | yes | 1.0000 | What is the whisky in this image? | p0199-jack-daniel-s-old-no-7 (Jack Daniel's Old No. 7) | p0199-jack-daniel-s-old-no-7, p0199-jack-daniel-s-single-barrel, p0128-george-dickel-no-12, p0128-george-dickel-barrel-select, p0113-early-times |
| citq006 | cropped_bottle_question | yes | yes | 1.0000 | What is the whisky in this image? | p0229-laphroaig-quarter-cask (Laphroaig Quarter Cask) | p0229-laphroaig-quarter-cask, p0228-laphroaig10-year-old, p0228-laphroaig-10-year-old-cask-strength, p0229-laphroaig-25-year-old, p0230-lark-s-single-malt |
| citq007 | cropped_bottle_question | yes | yes | 1.0000 | What is the whisky in this image? | p0225-lagavulin-distillers-edition (Lagavulin Distillers Edition) | p0225-lagavulin-distillers-edition, p0225-lagavulin-21-year-old, p0224-lagavulin-16-year-old, p0224-lagavulin-12-year-old |
| citq008 | cropped_bottle_question | yes | yes | 1.0000 | What is the whisky in this image? | p0021-ardbeg-10-year-old (Ardbeg 10 Year Old) | p0021-ardbeg-10-year-old |
| citq009 | cropped_bottle_question | yes | yes | 1.0000 | What is the whisky in this image? | p0244-the-macallan-30-year-old (The Macallan 30 Year Old) | p0244-the-macallan-30-year-old |
| citq010 | cropped_bottle_question | yes | yes | 1.0000 | What is the whisky in this image? | p0074-canadian-club-reserve (Canadian Club Reserve) | p0074-canadian-club-reserve, p0075-canadian-club-premium, p0075-canadian-club-classic, p0074-canadian-club-6-year-old-100-proof, p0376-windsor-canadian |
| citq011 | cropped_bottle_question | no | no | 0.0000 | What is the whisky in this image? | p0108-dimple-15-year-old (Dimple 15 Year Old) | p0108-dimple-15-year-old |
