# Gemini RAG Multimodal Store Query Summary

Store: `fileSearchStores/ragproductmultimodalstore-fdfd4rlokjnp`

## Overall Metrics

| Setting | Queries | Hit@1 | Hit@5 | MRR | Valid ID Rate | API Errors |
|---|---:|---:|---:|---:|---:|---:|
| Text -> multimodal RAG store | 20 | 0.7000 | 0.8500 | 0.7517 | 1.0000 | 0 |
| Image -> multimodal RAG store | 22 | 0.6818 | 0.6818 | 0.6818 | 0.9762 | 0 |
| Whole image + text -> multimodal RAG store | 11 | 0.7273 | 0.7273 | 0.7273 | 0.7778 | 0 |
| Cropped image + text -> multimodal RAG store | 11 | 0.5455 | 0.5455 | 0.5455 | 0.8077 | 0 |

## Hit@5 Misses

### Text -> multimodal RAG store
- `tq008` (semantic_brand_description): I want Irish whiskey from a Victorian distillery that sells both blends and single malts under the same name.
  - returned: p0239-locke-s-blend
- `tq018` (semantic_flavour): I want whisky with honey apples orchard fruit vanilla and a smooth easy palate.
  - returned: p0091-compass-box-asyla, p0303-robert-burns-single-malt, p0287-penderyn-peated, p0020-the-antiquary-12-year-old, p0152-glengoyne-10-year-old
- `tq020` (semantic_flavour): I want whisky with chocolate cocoa raisins figs and rich dessert notes.
  - returned: p0292-poit-dhubh-8-year-old, p0153-glengoyne-21-year-old, p0350-tomatin-25-year-old

### Image -> multimodal RAG store
- `iq001_crop` (cropped_bottle_identification): Macallan 1962 Fine & Rare
  - returned: p0231-the-last-drop
- `iq004_crop` (cropped_bottle_identification): Blanton's Bourbon
  - returned: p0108-dimple-15-year-old
- `iq006_crop` (cropped_bottle_identification): Laphroaig
  - returned: p0232-lauder-s
- `iq006_scene` (whole_scene_identification): Laphroaig
  - returned: p0232-lauder-s
- `iq007_crop` (cropped_bottle_identification): Lagavulin
  - returned: p0241-longmorn-16-year-old
- `iq011_crop` (cropped_bottle_identification): Johnnie Walker Blue Label
  - returned: p0367-whyte-mackay-special
- `iq011_scene` (whole_scene_identification): Johnnie Walker Blue Label
  - returned: p0267

### Whole image + text -> multimodal RAG store
- `itq006` (whole_scene_question): What is the whisky in this image?
  - returned: p0232-lauder-s.pdf
- `itq009` (whole_scene_question): What is the whisky in this image?
  - returned: p0070-bunnahabhain-18-year-old
- `itq011` (whole_scene_question): What is the whisky in this image?
  - returned: p0267-nikka-all-malt.pdf, p0052-black-bottle.pdf, p0052-black-bottle-10-year-old.pdf, p0328-strathisla-12-year-old.pdf, p0131-girvan-1964.pdf

### Cropped image + text -> multimodal RAG store
- `citq001` (cropped_bottle_question): What is the whisky in this image?
  - returned: p0231-the-last-drop
- `citq004` (cropped_bottle_question): What is the whisky in this image?
  - returned: p0161, p0108, p0232, p0173
- `citq006` (cropped_bottle_question): What is the whisky in this image?
  - returned: p0232
- `citq007` (cropped_bottle_question): What is the whisky in this image?
  - returned: p0104-dalwhinnie-15-year-old
- `citq011` (cropped_bottle_question): What is the whisky in this image?
  - returned: p0267-nikka-whiskey-from-the-barrel

## Query Results

### Text -> multimodal RAG store
| Query | Style | Hit@1 | Hit@5 | RR | Query / Reference | Top result | Returned IDs |
|---|---|---:|---:|---:|---|---|---|
| tq001 | metadata_brand | yes | yes | 1.0000 | I want an Ardbeg whisky. | p0022-ardbeg-uigeadail (ARDBEG UIGEADAIL) | p0022-ardbeg-uigeadail, p0021-ardbeg-airigh-nam-beist, p0022-ardbeg-blasda, p0021-ardbeg-10-year-old |
| tq002 | metadata_brand | yes | yes | 1.0000 | I want a Macallan whisky. | p0243-the-macallan-10-year-old (THE MACALLAN 10-YEAR-OLD) | p0243-the-macallan-10-year-old, p0244-the-macallan-25-year-old, p0244-the-macallan-30-year-old, p0243-the-macallan-fine-oak-10-year-old |
| tq003 | metadata_brand | yes | yes | 1.0000 | I want a Glenmorangie whisky. | p0158-glenmorangie-original (GLENMORANGIE ORIGINAL) | p0158-glenmorangie-original, p0158-glenmorangie-18-year-old, p0159-glenmorangie-25-year-old, p0159-glenmorangie-nectar-d-or |
| tq004 | metadata_brand | yes | yes | 1.0000 | I want a Johnnie Walker whisky. | p0209-johnnie-walker-gold-label (JOHNNIE WALKER GOLD LABEL) | p0209-johnnie-walker-gold-label, p0209-johnnie-walker-blue-label, p0208-johnnie-walker-black-label, p0208-johnnie-walker-green-label |
| tq005 | metadata_brand | yes | yes | 1.0000 | I want a Woodford Reserve bourbon. | p0378-woodford-reserve-distiller-s-select (WOODFORD RESERVE DISTILLERS SELECT) | p0378-woodford-reserve-distiller-s-select, p0378-master-s-collection-four-grain, p0379-master-s-collection-sonoma-cutrer-finish, p0379-master-s-collection-1838-sweet-mash |
| tq006 | semantic_brand_description | no | yes | 0.2000 | I want whisky from the southern coast of Islay, famous for pungent heavily peated malts. | p0228-laphroaig-10-year-old-cask-strength (LAPHROAIG 10-YEAR-OLD CASK STRENGTH) | p0228-laphroaig-10-year-old-cask-strength, p0229-laphroaig-quarter-cask, p0224-lagavulin-16-year-old, p0225-lagavulin-distillers-edition, p0021-ardbeg-10-year-old |
| tq007 | semantic_brand_description | yes | yes | 1.0000 | I want bourbon from a small Kentucky distillery that uses triple distillation and copper pot stills. | p0379-master-s-collection-sonoma-cutrer-finish (MASTERS COLLECTION SONOMA-CUTRER FINISH) | p0379-master-s-collection-sonoma-cutrer-finish, p0379-master-s-collection-1838-sweet-mash, p0378-master-s-collection-four-grain |
| tq008 | semantic_brand_description | no | no | 0.0000 | I want Irish whiskey from a Victorian distillery that sells both blends and single malts under the same name. | p0239-locke-s-blend (LOCKES BLEND) | p0239-locke-s-blend |
| tq009 | semantic_brand_description | yes | yes | 1.0000 | I want Japanese whisky from the country's first malt distillery, especially sweet fruity single malts and older sherry cask releases. | p0336-the-cask-of-yamazaki-1990-sherry-butt (THE CASK OF YAMAZAKI 1990 SHERRY BUTT) | p0336-the-cask-of-yamazaki-1990-sherry-butt, p0336-suntory-vintage-1984, p0335-the-yamazaki-12-year-old |
| tq010 | semantic_brand_description | yes | yes | 1.0000 | I want Islay whisky from the shore of Loch Indaal, a distillery revived by Murray McDavid that bottles on the island. | p0066-bruichladdich-waves (BRUICHLADDICH WAVES) | p0066-bruichladdich-waves |
| tq011 | metadata_abv | yes | yes | 1.0000 | I want an Ardbeg whisky around 40 percent ABV. | p0022-ardbeg-blasda (ARDBEG BLASDA) | p0022-ardbeg-blasda |
| tq012 | metadata_abv | yes | yes | 1.0000 | I want Bruichladdich single malts bottled at 46 percent ABV. | p0065-bruichladdich-21-year-old (BRUICHLADDICH 21-YEAR-OLD) | p0065-bruichladdich-21-year-old, p0065-bruichladdich-18-year-old, p0066-bruichladdich-waves |
| tq013 | metadata_abv | yes | yes | 1.0000 | I want a very high proof bourbon over 60 percent ABV. | p0129-george-t-stagg-2008-edition (GEORGE T. STAGG 2008 EDITION) | p0129-george-t-stagg-2008-edition, p0059-booker-s-kentucky-straight |
| tq014 | metadata_abv | yes | yes | 1.0000 | I want Laphroaig cask strength whisky around 57 percent ABV. | p0228-laphroaig-10-year-old-cask-strength (LAPHROAIG 10-YEAR-OLD CASK STRENGTH) | p0228-laphroaig-10-year-old-cask-strength |
| tq015 | semantic_flavour | yes | yes | 1.0000 | I want smoky peaty whisky with seaweed iodine tar and a long coastal finish. | p0228-laphroaig-10-year-old-cask-strength (LAPHROAIG 10-YEAR-OLD CASK STRENGTH) | p0228-laphroaig-10-year-old-cask-strength, p0224-lagavulin-16-year-old, p0228-laphroaig10-year-old, p0337-talisker-10-year-old, p0233-ledaig-10-year-old |
| tq016 | semantic_flavour | no | yes | 0.3333 | I want sherry matured whisky with raisins fruitcake oloroso spice and rich sweetness. | p0169-grant-s-sherry-cask-reserve (GRANTS SHERRY CASK RESERVE) | p0169-grant-s-sherry-cask-reserve, p0153-glengoyne-21-year-old, p0147-glenfarclas-12-year-old, p0144-glendronach-12-year-old, p0127-frysk-hynder-sherry-matured |
| tq017 | semantic_flavour | no | yes | 0.5000 | I want bourbon with vanilla caramel honey oak and a rounded sweet palate. | p0359-pappy-van-winkle-s-family-reserve-15-year-old (PAPPY VAN WINKLES FAMILY RESERVE 15-YEAR-OLD) | p0359-pappy-van-winkle-s-family-reserve-15-year-old, p0069-bulleit-bourbon, p0359-old-rip-van-winkle-10-year-old, p0032-baker-s-7-year-old, p0112-eagle-rare-2008-edition |
| tq018 | semantic_flavour | no | no | 0.0000 | I want whisky with honey apples orchard fruit vanilla and a smooth easy palate. | p0091-compass-box-asyla (COMPASS BOX ASYLA) | p0091-compass-box-asyla, p0303-robert-burns-single-malt, p0287-penderyn-peated, p0020-the-antiquary-12-year-old, p0152-glengoyne-10-year-old |
| tq019 | semantic_flavour | yes | yes | 1.0000 | I want rye whiskey with pepper mint spice oak and a dry finish. | p0310-russell-s-reserve-rye (RUSSELLS RESERVE RYE) | p0310-russell-s-reserve-rye, p0302-rittenhouse-rye-21-year-old, p0302-rittenhouse-rye-100-proof |
| tq020 | semantic_flavour | no | no | 0.0000 | I want whisky with chocolate cocoa raisins figs and rich dessert notes. | p0292-poit-dhubh-8-year-old (POIT DHUBH 8-YEAR-OLD) | p0292-poit-dhubh-8-year-old, p0153-glengoyne-21-year-old, p0350-tomatin-25-year-old |

### Image -> multimodal RAG store
| Query | Style | Hit@1 | Hit@5 | RR | Query / Reference | Top result | Returned IDs |
|---|---|---:|---:|---:|---|---|---|
| iq001_crop | cropped_bottle_identification | no | no | 0.0000 | Macallan 1962 Fine & Rare | p0231-the-last-drop (THE LAST DROP) | p0231-the-last-drop |
| iq001_scene | whole_scene_identification | yes | yes | 1.0000 | Macallan 1962 Fine & Rare | p0243-the-macallan-10-year-old (THE MACALLAN 10-YEAR-OLD) | p0243-the-macallan-10-year-old, p0244-the-macallan-25-year-old, p0244-the-macallan-30-year-old, p0243-the-macallan-fine-oak-10-year-old, p0262-miltonduff-gordon-macphail-1968 |
| iq002_crop | cropped_bottle_identification | yes | yes | 1.0000 | Suntory Hibiki 17 | p0334-suntory-hibiki-17-year-old (SUNTORY HIBIKI 17-YEAR-OLD) | p0334-suntory-hibiki-17-year-old |
| iq002_scene | whole_scene_identification | yes | yes | 1.0000 | Suntory Hibiki 17 | p0334-suntory-hibiki-17-year-old (SUNTORY HIBIKI 17-YEAR-OLD) | p0334-suntory-hibiki-17-year-old |
| iq003_crop | cropped_bottle_identification | yes | yes | 1.0000 | Johnnie Walker Black Label | p0208-johnnie-walker-black-label (JOHNNIE WALKER BLACK LABEL) | p0208-johnnie-walker-black-label |
| iq003_scene | whole_scene_identification | yes | yes | 1.0000 | Johnnie Walker Black Label | p0208-johnnie-walker-black-label (JOHNNIE WALKER BLACK LABEL) | p0208-johnnie-walker-black-label |
| iq004_crop | cropped_bottle_identification | no | no | 0.0000 | Blanton's Bourbon | p0108-dimple-15-year-old (DIMPLE 15-YEAR-OLD) | p0108-dimple-15-year-old |
| iq004_scene | whole_scene_identification | yes | yes | 1.0000 | Blanton's Bourbon | p0057-blanton-s-single-barrel (BLANTON'S SINGLE BARREL) | p0057-blanton-s-single-barrel |
| iq005_crop | cropped_bottle_identification | yes | yes | 1.0000 | Jack Daniel's Old No. 7 | p0199-jack-daniel-s-old-no-7 (JACK DANIELS OLD NO. 7) | p0199-jack-daniel-s-old-no-7, p0199-jack-daniel-s-single-barrel |
| iq005_scene | whole_scene_identification | yes | yes | 1.0000 | Jack Daniel's Old No. 7 | p0199-jack-daniel-s-old-no-7 (JACK DANIELS OLD NO. 7) | p0199-jack-daniel-s-old-no-7, p0199-jack-daniel-s-single-barrel |
| iq006_crop | cropped_bottle_identification | no | no | 0.0000 | Laphroaig | p0232-lauder-s (LAUDERS) | p0232-lauder-s |
| iq006_scene | whole_scene_identification | no | no | 0.0000 | Laphroaig | p0232-lauder-s (Lauder's Finest Scotch Whisky) | p0232-lauder-s |
| iq007_crop | cropped_bottle_identification | no | no | 0.0000 | Lagavulin | p0241-longmorn-16-year-old (LONGMORN 16-YEAR-OLD) | p0241-longmorn-16-year-old |
| iq007_scene | whole_scene_identification | yes | yes | 1.0000 | Lagavulin | p0224-lagavulin-16-year-old (LAGAVULIN 16-YEAR-OLD) | p0224-lagavulin-16-year-old, p0225-lagavulin-distillers-edition, p0224-lagavulin-12-year-old, p0225-lagavulin-21-year-old |
| iq008_crop | cropped_bottle_identification | yes | yes | 1.0000 | Ardbeg 10 | p0021-ardbeg-10-year-old (ARDBEG 10-YEAR-OLD) | p0021-ardbeg-10-year-old |
| iq008_scene | whole_scene_identification | yes | yes | 1.0000 | Ardbeg 10 | p0021-ardbeg-10-year-old (ARDBEG 10-YEAR-OLD) | p0021-ardbeg-10-year-old, p0021-ardbeg-airigh-nam-beist, p0022-ardbeg-blasda, p0022-ardbeg-uigeadail, p0023-ardmore-traditional-cask |
| iq009_crop | cropped_bottle_identification | yes | yes | 1.0000 | Macallan 18 | p0244-the-macallan-30-year-old (THE MACALLAN 30-YEAR-OLD) | p0244-the-macallan-30-year-old |
| iq009_scene | whole_scene_identification | yes | yes | 1.0000 | Macallan 18 | p0244-the-macallan-30-year-old (THE MACALLAN 30-YEAR-OLD) | p0244-the-macallan-30-year-old |
| iq010_crop | cropped_bottle_identification | yes | yes | 1.0000 | Canadian Club | p0075-canadian-club-premium (CANADIAN CLUB PREMIUM) | p0075-canadian-club-premium, p0075-canadian-club-classic, p0074-canadian-club-reserve, p0074-canadian-club-6-year-old-100-proof, p0376-windsor-canadian |
| iq010_scene | whole_scene_identification | yes | yes | 1.0000 | Canadian Club | p0075-canadian-club-classic (CANADIAN CLUB CLASSIC) | p0075-canadian-club-classic, p0075-canadian-club-premium, p0074-canadian-club-reserve, p0074-canadian-club-6-year-old-100-proof |
| iq011_crop | cropped_bottle_identification | no | no | 0.0000 | Johnnie Walker Blue Label | p0367-whyte-mackay-special (Whyte & Mackay Special) | p0367-whyte-mackay-special |
| iq011_scene | whole_scene_identification | no | no | 0.0000 | Johnnie Walker Blue Label | p0267 (Nikka Whisky From The Barrel) | p0267 |

### Whole image + text -> multimodal RAG store
| Query | Style | Hit@1 | Hit@5 | RR | Query / Reference | Top result | Returned IDs |
|---|---|---:|---:|---:|---|---|---|
| itq001 | whole_scene_question | yes | yes | 1.0000 | What is the whisky in this image? | p0243-the-macallan-10-year-old (THE MACALLAN 10-YEAR-OLD) | p0243-the-macallan-10-year-old, p0244-the-macallan-25-year-old, p0244-the-macallan-30-year-old, p0243-the-macallan-fine-oak-10-year-old, p0262-miltonduff-gordon-macphail-1968 |
| itq002 | whole_scene_question | yes | yes | 1.0000 | What is the whisky in this image? | p0334-suntory-hibiki-17-year-old (SUNTORY HIBIKI 17-YEAR-OLD) | p0334-suntory-hibiki-17-year-old |
| itq003 | whole_scene_question | yes | yes | 1.0000 | What is the whisky in this image? | p0208-johnnie-walker-black-label (JOHNNIE WALKER BLACK LABEL) | p0208-johnnie-walker-black-label |
| itq004 | whole_scene_question | yes | yes | 1.0000 | What is the whisky in this image? | p0057-blanton-s-single-barrel (Blanton's Single Barrel) | p0057-blanton-s-single-barrel |
| itq005 | whole_scene_question | yes | yes | 1.0000 | What is the whisky in this image? | p0199-jack-daniel-s-old-no-7 (JACK DANIELS OLD NO. 7) | p0199-jack-daniel-s-old-no-7, p0199-jack-daniel-s-single-barrel |
| itq006 | whole_scene_question | no | no | 0.0000 | What is the whisky in this image? | p0232-lauder-s.pdf (Lauder's Finest Scotch Whisky) | p0232-lauder-s.pdf |
| itq007 | whole_scene_question | yes | yes | 1.0000 | What is the whisky in this image? | p0224-lagavulin-16-year-old (LAGAVULIN 16-YEAR-OLD) | p0224-lagavulin-16-year-old, p0225-lagavulin-distillers-edition, p0224-lagavulin-12-year-old, p0225-lagavulin-21-year-old |
| itq008 | whole_scene_question | yes | yes | 1.0000 | What is the whisky in this image? | p0021-ardbeg-10-year-old (ARDBEG 10-YEAR-OLD) | p0021-ardbeg-10-year-old |
| itq009 | whole_scene_question | no | no | 0.0000 | What is the whisky in this image? | p0070-bunnahabhain-18-year-old (BUNNAHABHAIN 18-YEAR-OLD) | p0070-bunnahabhain-18-year-old |
| itq010 | whole_scene_question | yes | yes | 1.0000 | What is the whisky in this image? | p0074-canadian-club-reserve (CANADIAN CLUB RESERVE) | p0074-canadian-club-reserve, p0074-canadian-club-6-year-old-100-proof, p0075-canadian-club-premium, p0075-canadian-club-classic, p0076-canadian-mist |
| itq011 | whole_scene_question | no | no | 0.0000 | What is the whisky in this image? | p0267-nikka-all-malt.pdf (Nikka Whisky From The Barrel) | p0267-nikka-all-malt.pdf, p0052-black-bottle.pdf, p0052-black-bottle-10-year-old.pdf, p0328-strathisla-12-year-old.pdf, p0131-girvan-1964.pdf |

### Cropped image + text -> multimodal RAG store
| Query | Style | Hit@1 | Hit@5 | RR | Query / Reference | Top result | Returned IDs |
|---|---|---:|---:|---:|---|---|---|
| citq001 | cropped_bottle_question | no | no | 0.0000 | What is the whisky in this image? | p0231-the-last-drop (THE LAST DROP) | p0231-the-last-drop |
| citq002 | cropped_bottle_question | yes | yes | 1.0000 | What is the whisky in this image? | p0334-suntory-hibiki-17-year-old (SUNTORY HIBIKI 17-YEAR-OLD) | p0334-suntory-hibiki-17-year-old |
| citq003 | cropped_bottle_question | yes | yes | 1.0000 | What is the whisky in this image? | p0208-johnnie-walker-black-label (JOHNNIE WALKER BLACK LABEL) | p0208-johnnie-walker-black-label |
| citq004 | cropped_bottle_question | no | no | 0.0000 | What is the whisky in this image? | p0161 (The Glenrothes Select Reserve) | p0161, p0108, p0232, p0173 |
| citq005 | cropped_bottle_question | yes | yes | 1.0000 | What is the whisky in this image? | p0199-jack-daniel-s-old-no-7 (JACK DANIELS OLD NO. 7) | p0199-jack-daniel-s-old-no-7, p0199-jack-daniel-s-single-barrel, p0128-george-dickel-no-12, p0128-george-dickel-barrel-select, p0278-old-grand-dad |
| citq006 | cropped_bottle_question | no | no | 0.0000 | What is the whisky in this image? | p0232 (Lauder's Finest Scotch Whisky) | p0232 |
| citq007 | cropped_bottle_question | no | no | 0.0000 | What is the whisky in this image? | p0104-dalwhinnie-15-year-old (DALWHINNIE 15-YEAR-OLD) | p0104-dalwhinnie-15-year-old |
| citq008 | cropped_bottle_question | yes | yes | 1.0000 | What is the whisky in this image? | p0021-ardbeg-10-year-old (ARDBEG 10-YEAR-OLD) | p0021-ardbeg-10-year-old |
| citq009 | cropped_bottle_question | yes | yes | 1.0000 | What is the whisky in this image? | p0244-the-macallan-25-year-old (THE MACALLAN 25-YEAR-OLD) | p0244-the-macallan-25-year-old, p0244-the-macallan-30-year-old, p0243-the-macallan-10-year-old, p0243-the-macallan-fine-oak-10-year-old, p0070-bunnahabhain-18-year-old |
| citq010 | cropped_bottle_question | yes | yes | 1.0000 | What is the whisky in this image? | p0075-canadian-club-premium (CANADIAN CLUB PREMIUM) | p0075-canadian-club-premium, p0075-canadian-club-classic, p0074-canadian-club-reserve, p0074-canadian-club-6-year-old-100-proof, p0377-wiser-s-deluxe |
| citq011 | cropped_bottle_question | no | no | 0.0000 | What is the whisky in this image? | p0267-nikka-whiskey-from-the-barrel (Nikka Whisky From The Barrel) | p0267-nikka-whiskey-from-the-barrel |
