# Gemini RAG Text Query Summary

Source report: `data/eval/gemini_rag_text_report.json`

## Overall Metrics

- hit@1: 0.8000
- hit@5: 0.9000
- MRR: 0.8292
- valid product ID rate: 1.0000

## Query Results

| Query | Style | Hit@1 | Hit@5 | RR | User query | Top result | Top returned IDs |
|---|---|---:|---:|---:|---|---|---|
| tq001 | metadata_brand | yes | yes | 1.0000 | I want an Ardbeg whisky. | p0021-ardbeg-10-year-old (ARDBEG 10-YEAR-OLD) | p0021-ardbeg-10-year-old, p0022-ardbeg-uigeadail, p0021-ardbeg-airigh-nam-beist, p0022-ardbeg-blasda |
| tq002 | metadata_brand | yes | yes | 1.0000 | I want a Macallan whisky. | p0243-the-macallan-10-year-old (THE MACALLAN 10-YEAR-OLD) | p0243-the-macallan-10-year-old, p0243-the-macallan-fine-oak-10-year-old, p0244-the-macallan-30-year-old, p0244-the-macallan-25-year-old |
| tq003 | metadata_brand | yes | yes | 1.0000 | I want a Glenmorangie whisky. | p0158-glenmorangie-18-year-old (GLENMORANGIE 18-YEAR-OLD) | p0158-glenmorangie-18-year-old, p0158-glenmorangie-original, p0159-glenmorangie-25-year-old, p0159-glenmorangie-nectar-d-or |
| tq004 | metadata_brand | yes | yes | 1.0000 | I want a Johnnie Walker whisky. | p0209-johnnie-walker-blue-label (JOHNNIE WALKER BLUE LABEL) | p0209-johnnie-walker-blue-label, p0209-johnnie-walker-gold-label, p0208-johnnie-walker-green-label, p0208-johnnie-walker-black-label |
| tq005 | metadata_brand | yes | yes | 1.0000 | I want a Woodford Reserve bourbon. | p0378-woodford-reserve-distiller-s-select (WOODFORD RESERVE DISTILLERS SELECT) | p0378-woodford-reserve-distiller-s-select, p0379-master-s-collection-1838-sweet-mash, p0378-master-s-collection-four-grain, p0379-master-s-collection-sonoma-cutrer-finish |
| tq006 | semantic_brand_description | no | no | 0.0000 | I want whisky from the southern coast of Islay, famous for pungent heavily peated malts. | p0228-laphroaig10-year-old (LAPHROAIG10-YEAR-OLD) | p0228-laphroaig10-year-old, p0228-laphroaig-10-year-old-cask-strength, p0224-lagavulin-16-year-old |
| tq007 | semantic_brand_description | yes | yes | 1.0000 | I want bourbon from a small Kentucky distillery that uses triple distillation and copper pot stills. | p0378-woodford-reserve-distiller-s-select (WOODFORD RESERVE DISTILLERS SELECT) | p0378-woodford-reserve-distiller-s-select, p0379-master-s-collection-1838-sweet-mash, p0378-master-s-collection-four-grain |
| tq008 | semantic_brand_description | yes | yes | 1.0000 | I want Irish whiskey from a Victorian distillery that sells both blends and single malts under the same name. | p0071-bushmills-original (BUSHMILLS ORIGINAL) | p0071-bushmills-original, p0071-bushmills-black-bush, p0072-bushmills-malt-10-year-old, p0072-bushmills-malt-16-year-old |
| tq009 | semantic_brand_description | yes | yes | 1.0000 | I want Japanese whisky from the country's first malt distillery, especially sweet fruity single malts and older sherry cask releases. | p0336-the-cask-of-yamazaki-1990-sherry-butt (THE CASK OF YAMAZAKI 1990 SHERRY BUTT) | p0336-the-cask-of-yamazaki-1990-sherry-butt, p0336-suntory-vintage-1984, p0335-the-yamazaki-12-year-old, p0218-karuizawa-1986-cask-no-7387-bottled-2008, p0331-suntory-hakushu-12-year-old |
| tq010 | semantic_brand_description | yes | yes | 1.0000 | I want Islay whisky from the shore of Loch Indaal, a distillery revived by Murray McDavid that bottles on the island. | p0066-bruichladdich-waves (BRUICHLADDICH WAVES) | p0066-bruichladdich-waves, p0065-bruichladdich-18-year-old, p0066-bruichladdich-peat |
| tq011 | metadata_abv | yes | yes | 1.0000 | I want an Ardbeg whisky around 40 percent ABV. | p0022-ardbeg-blasda (ARDBEG BLASDA) | p0022-ardbeg-blasda |
| tq012 | metadata_abv | yes | yes | 1.0000 | I want Bruichladdich single malts bottled at 46 percent ABV. | p0066-bruichladdich-peat (BRUICHLADDICH PEAT) | p0066-bruichladdich-peat, p0065-bruichladdich-18-year-old, p0066-bruichladdich-waves |
| tq013 | metadata_abv | yes | yes | 1.0000 | I want a very high proof bourbon over 60 percent ABV. | p0129-george-t-stagg-2008-edition (GEORGE T. STAGG 2008 EDITION) | p0129-george-t-stagg-2008-edition, p0059-booker-s-kentucky-straight |
| tq014 | metadata_abv | yes | yes | 1.0000 | I want Laphroaig cask strength whisky around 57 percent ABV. | p0228-laphroaig-10-year-old-cask-strength (LAPHROAIG 10-YEAR-OLD CASK STRENGTH) | p0228-laphroaig-10-year-old-cask-strength |
| tq015 | semantic_flavour | yes | yes | 1.0000 | I want smoky peaty whisky with seaweed iodine tar and a long coastal finish. | p0228-laphroaig-10-year-old-cask-strength (LAPHROAIG 10-YEAR-OLD CASK STRENGTH) | p0228-laphroaig-10-year-old-cask-strength, p0242-longrow-14-year-old, p0066-bruichladdich-peat, p0228-laphroaig10-year-old, p0233-ledaig-10-year-old |
| tq016 | semantic_flavour | no | yes | 0.3333 | I want sherry matured whisky with raisins fruitcake oloroso spice and rich sweetness. | p0328-strathisla-12-year-old (STRATHISLA 12-YEAR-OLD) | p0328-strathisla-12-year-old, p0348-tobermory-15-year-old, p0013-aberlour-12-year-old-sherry-matured, p0153-glengoyne-21-year-old, p0147-glenfarclas-12-year-old |
| tq017 | semantic_flavour | yes | yes | 1.0000 | I want bourbon with vanilla caramel honey oak and a rounded sweet palate. | p0117-elijah-craig-12-year-old (ELIJAH CRAIG 12-YEAR-OLD) | p0117-elijah-craig-12-year-old, p0277-old-forester-birthday-bourbon-2007, p0069-bulleit-bourbon, p0359-old-rip-van-winkle-10-year-old, p0015-american-spirit-15-year-old |
| tq018 | semantic_flavour | no | yes | 0.2500 | I want whisky with honey apples orchard fruit vanilla and a smooth easy palate. | p0091-compass-box-asyla (COMPASS BOX ASYLA) | p0091-compass-box-asyla, p0303-robert-burns-single-malt, p0252-mcclelland-s-highland, p0012-aberfeldy-12-year-old, p0308-royal-lochnagar-selected-reserve |
| tq019 | semantic_flavour | yes | yes | 1.0000 | I want rye whiskey with pepper mint spice oak and a dry finish. | p0310-russell-s-reserve-rye (RUSSELLS RESERVE RYE) | p0310-russell-s-reserve-rye, p0280-old-potrero-rye, p0302-rittenhouse-rye-21-year-old, p0302-rittenhouse-rye-100-proof, p0346-templeton-rye-small-batch |
| tq020 | semantic_flavour | no | no | 0.0000 | I want whisky with chocolate cocoa raisins figs and rich dessert notes. | p0190-five-of-spades-distilled-2000-bottled-2008 (FIVE OF SPADES, DISTILLED 2000, BOTTLED 2008) | p0190-five-of-spades-distilled-2000-bottled-2008, p0156-the-glenlivet-xxv, p0328-strathisla-12-year-old, p0153-glengoyne-21-year-old |

## Hit@5 Misses

- `tq006` (semantic_brand_description): I want whisky from the southern coast of Islay, famous for pungent heavily peated malts.
  - returned: p0228-laphroaig10-year-old, p0228-laphroaig-10-year-old-cask-strength, p0224-lagavulin-16-year-old
- `tq020` (semantic_flavour): I want whisky with chocolate cocoa raisins figs and rich dessert notes.
  - returned: p0190-five-of-spades-distilled-2000-bottled-2008, p0156-the-glenlivet-xxv, p0328-strathisla-12-year-old, p0153-glengoyne-21-year-old
