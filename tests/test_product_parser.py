from __future__ import annotations

import unittest
from pathlib import Path
from typing import Any

from rs_demo.product_parser import (
    ProductParser,
    clean_lines,
    parse_age,
    parse_page,
    parse_pages,
    parse_spec,
)


FIXTURE_ROOT = Path("data/extracted/pymupdf_probe")


def require_page(page_number: int) -> Path:
    page_dir = FIXTURE_ROOT / f"page_{page_number:04d}"
    if not (page_dir / "text.txt").exists():
        raise unittest.SkipTest(f"missing extracted text fixture: {page_dir / 'text.txt'}")
    return page_dir


def records_by_name(page_number: int) -> dict[str, dict[str, Any]]:
    return {record["name"]: record for record in parse_page(require_page(page_number))}


class ParserPrimitiveTests(unittest.TestCase):
    def test_clean_lines_removes_page_noise(self) -> None:
        text = (require_page(21) / "text.txt").read_text(encoding="utf-8")

        lines = clean_lines(text)

        self.assertEqual(lines[0], "ARDBEG")
        self.assertNotIn("W H I S K E Y S", lines)

    def test_parse_spec_extracts_style_region_and_abv(self) -> None:
        style, region, abv = parse_spec("SINGLE MALT: ISLAY 46% ABV")

        self.assertEqual(style, "Single Malt")
        self.assertEqual(region, "Islay")
        self.assertEqual(abv, 46.0)

    def test_parse_age_from_product_name(self) -> None:
        self.assertEqual(parse_age("ARDBEG 10-YEAR-OLD"), 10)

    def test_product_parser_class_matches_function_api(self) -> None:
        self.assertEqual(ProductParser().parse_page(require_page(24)), parse_page(require_page(24)))


class PageParserRegressionTests(unittest.TestCase):
    def test_page_21_ardbeg_two_product_records(self) -> None:
        records = records_by_name(21)

        self.assertEqual(
            set(records),
            {"ARDBEG 10-YEAR-OLD", "ARDBEG AIRIGH NAM BEIST"},
        )

        ten_year = records["ARDBEG 10-YEAR-OLD"]
        self.assertEqual(ten_year["brand_or_distillery"], "ARDBEG")
        self.assertEqual(ten_year["country"], "Scotland")
        self.assertEqual(ten_year["region"], "Islay")
        self.assertEqual(ten_year["style"], "Single Malt")
        self.assertEqual(ten_year["age"], 10)
        self.assertEqual(ten_year["abv"], 46.0)
        self.assertIn("smoked fish", ten_year["description"])
        self.assertEqual(ten_year["image_confidence"], "medium")

        airigh = records["ARDBEG AIRIGH NAM BEIST"]
        self.assertEqual(airigh["region"], "Islay")
        self.assertEqual(airigh["abv"], 46.0)
        self.assertIn("vanilla notes", airigh["description"])
        self.assertEqual(airigh["image_confidence"], "low")

    def test_page_22_continuation_page_keeps_products_without_country(self) -> None:
        records = records_by_name(22)

        self.assertEqual(set(records), {"ARDBEG BLASDA", "ARDBEG UIGEADAIL"})
        self.assertIsNone(records["ARDBEG BLASDA"]["country"])
        self.assertIn("In 1997, Ardbeg was rescued", records["ARDBEG BLASDA"]["brand_description"])
        self.assertEqual(records["ARDBEG BLASDA"]["region"], "Islay")
        self.assertEqual(records["ARDBEG BLASDA"]["abv"], 40.0)
        self.assertEqual(records["ARDBEG UIGEADAIL"]["abv"], 54.2)
        self.assertIn("molasseslike sweetness", records["ARDBEG UIGEADAIL"]["description"])

    def test_page_24_armorik_single_record(self) -> None:
        records = records_by_name(24)

        self.assertEqual(set(records), {"ARMORIK WHISKEY BRETON"})
        armorik = records["ARMORIK WHISKEY BRETON"]
        self.assertEqual(armorik["brand_or_distillery"], "ARMORIK")
        self.assertEqual(armorik["country"], "France")
        self.assertEqual(armorik["style"], "Single Malt")
        self.assertEqual(armorik["abv"], 40.0)
        self.assertEqual(armorik["image_confidence"], "high")
        self.assertIn("salty tang", armorik["description"])

    def test_page_14_does_not_split_description_containing_rye_whiskey(self) -> None:
        records = records_by_name(14)

        self.assertEqual(set(records), {"ALBERTA SPRINGS 10-YEAR-OLD", "ALBERTA PREMIUM"})
        premium = records["ALBERTA PREMIUM"]
        self.assertEqual(premium["style"], "Canadian Rye")
        self.assertEqual(premium["abv"], 40.0)
        self.assertIn("Special Mild Canadian Rye Whiskey", premium["description"])
        self.assertNotIn("Described as", records)

    def test_page_15_multiline_brand_heading(self) -> None:
        records = records_by_name(15)

        self.assertEqual(set(records), {"AMERICAN SPIRIT 15-YEAR-OLD"})
        product = records["AMERICAN SPIRIT 15-YEAR-OLD"]
        self.assertEqual(product["brand_or_distillery"], "AMERICAN SPIRIT")
        self.assertEqual(product["country"], "USA")
        self.assertEqual(product["style"], "Bourbon")
        self.assertEqual(product["age"], 15)
        self.assertEqual(product["abv"], 50.0)

    def test_page_16_style_words_can_be_part_of_product_name(self) -> None:
        records = records_by_name(16)

        self.assertEqual(
            set(records),
            {
                "AMRUT INDIAN SINGLE MALT CASK STRENGTH",
                "AMRUT PEATED INDIAN SINGLE MALT",
            },
        )
        peated = records["AMRUT PEATED INDIAN SINGLE MALT"]
        self.assertEqual(peated["style"], "Single Malt")
        self.assertEqual(peated["abv"], 62.78)
        self.assertIn("kippery smoke", peated["description"])

    def test_page_73_single_grain_style(self) -> None:
        records = records_by_name(73)

        self.assertEqual(set(records), {"CAMERON BRIG 12-YEAR-OLD"})
        product = records["CAMERON BRIG 12-YEAR-OLD"]
        self.assertEqual(product["style"], "Single Grain")
        self.assertEqual(product["abv"], 40.0)
        self.assertIn("clean and grassy", product["description"])

    def test_page_81_double_barrel_whiskey_style(self) -> None:
        records = records_by_name(81)

        self.assertEqual(set(records), {"CHARBAY DOUBLE BARREL"})
        product = records["CHARBAY DOUBLE BARREL"]
        self.assertEqual(product["style"], "Double Barrel Whiskey")
        self.assertEqual(product["abv"], 64.0)

    def test_page_110_irish_pot_still_whiskey_style(self) -> None:
        records = records_by_name(110)

        self.assertEqual(set(records), {"DUNGOURNEY 1964"})
        product = records["DUNGOURNEY 1964"]
        self.assertEqual(product["style"], "Irish Pot Still Whiskey")
        self.assertEqual(product["abv"], 40.0)

    def test_page_119_new_make_style(self) -> None:
        records = records_by_name(119)

        self.assertEqual(set(records), {"ENGLISH WHISKY CO. CHAPTER 3"})
        product = records["ENGLISH WHISKY CO. CHAPTER 3"]
        self.assertEqual(product["style"], "New Make")
        self.assertEqual(product["abv"], 40.0)

    def test_page_222_poteen_style(self) -> None:
        records = records_by_name(222)

        self.assertEqual(set(records), {"KNOCKEEN HILLS 60", "KNOCKEEN HILLS 70"})
        self.assertEqual(records["KNOCKEEN HILLS 60"]["style"], "Poteen")
        self.assertEqual(records["KNOCKEEN HILLS 60"]["abv"], 60.0)
        self.assertEqual(records["KNOCKEEN HILLS 70"]["abv"], 70.0)

    def test_page_376_blended_canadian_rye_style(self) -> None:
        records = records_by_name(376)

        self.assertEqual(set(records), {"WINDSOR CANADIAN"})
        product = records["WINDSOR CANADIAN"]
        self.assertEqual(product["style"], "Blended Canadian Rye")
        self.assertEqual(product["abv"], 40.0)

    def test_page_113_kentucky_whiskey_style(self) -> None:
        records = records_by_name(113)

        self.assertEqual(set(records), {"EARLY TIMES"})
        self.assertEqual(records["EARLY TIMES"]["style"], "Kentucky Whiskey")

    def test_page_115_oregon_whiskey_style(self) -> None:
        records = records_by_name(115)

        self.assertEqual(set(records), {"EDGEFIELD HOGSHEAD"})
        self.assertEqual(records["EDGEFIELD HOGSHEAD"]["style"], "Oregon Whiskey")

    def test_page_166_mixed_grain_whiskey_style(self) -> None:
        records = records_by_name(166)

        self.assertEqual(set(records), {"GOLDLYS 10-YEAR-OLD"})
        self.assertEqual(records["GOLDLYS 10-YEAR-OLD"]["style"], "Mixed Grain Whiskey")

    def test_page_170_pure_pot_still_style(self) -> None:
        records = records_by_name(170)

        self.assertEqual(set(records), {"GREEN SPOT"})
        self.assertEqual(records["GREEN SPOT"]["style"], "Pure Pot Still")

    def test_page_327_colorado_whiskey_style(self) -> None:
        records = records_by_name(327)

        self.assertEqual(set(records), {"STRANAHAN’S COLORADO WHISKEY"})
        self.assertEqual(records["STRANAHAN’S COLORADO WHISKEY"]["style"], "Colorado Whiskey")

    def test_page_345_plain_malt_style(self) -> None:
        records = records_by_name(345)

        self.assertEqual(set(records), {"TEERENPELI 3-YEAR-OLD NO. 001", "TEERENPELI 6-YEAR-OLD"})
        self.assertEqual(records["TEERENPELI 3-YEAR-OLD NO. 001"]["style"], "Malt")

    def test_brand_enrichment_combines_ardbeg_description_across_pages(self) -> None:
        records = {
            record["product_id"]: record
            for record in parse_pages(FIXTURE_ROOT)
            if record["brand_or_distillery"] == "ARDBEG"
        }

        ardbeg_ids = {
            "p0021-ardbeg-10-year-old",
            "p0021-ardbeg-airigh-nam-beist",
            "p0022-ardbeg-blasda",
            "p0022-ardbeg-uigeadail",
        }
        self.assertEqual(set(records), ardbeg_ids)

        descriptions = {record["brand_description"] for record in records.values()}
        self.assertEqual(len(descriptions), 1)
        description = descriptions.pop()
        self.assertIn("spiritual home of Scotland’s pungent", description)
        self.assertIn("In 1997, Ardbeg was rescued", description)
        self.assertIn("growing cult status", description)

        for record in records.values():
            self.assertEqual(record["country"], "Scotland")
            self.assertEqual(record["website"], "www.ardbeg.com")

    def test_brand_enrichment_reassigns_woodford_reserve_continuation_page(self) -> None:
        records = {
            record["product_id"]: record
            for record in parse_pages(FIXTURE_ROOT)
            if record["source_page"] in {378, 379}
        }

        woodford_ids = {
            "p0378-woodford-reserve-distiller-s-select",
            "p0378-master-s-collection-four-grain",
            "p0379-master-s-collection-sonoma-cutrer-finish",
            "p0379-master-s-collection-1838-sweet-mash",
        }
        self.assertEqual(set(records), woodford_ids)

        descriptions = {record["brand_description"] for record in records.values()}
        self.assertEqual(len(descriptions), 1)
        description = descriptions.pop()
        self.assertIn("Woodford Reserve is the smallest distillery", description)
        self.assertIn("first bottling in the Master’s Collection range", description)

        for record in records.values():
            self.assertEqual(record["brand_or_distillery"], "WOODFORD RESERVE")
            self.assertEqual(record["country"], "USA")
            self.assertEqual(record["website"], "www.woodfordreserve.com")

        sweet_mash = records["p0379-master-s-collection-1838-sweet-mash"]
        self.assertEqual(
            sweet_mash["description"],
            (
                "Maple syrup, spicy fruit, cinnamon, and nutmeg aromas. Rich palate, "
                "with more maple syrup, rich fruit, rye, and mint. Lengthy finish, "
                "with soft apple notes."
            ),
        )
        self.assertNotIn("In 2005", sweet_mash["description"])


if __name__ == "__main__":
    unittest.main()
