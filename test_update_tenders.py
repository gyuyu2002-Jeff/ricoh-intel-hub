import unittest

from update_tenders import classify_tender_relevance


def announcement(title, category=""):
    return {"brief": {"title": title, "category": category}}


class TenderRelevanceTests(unittest.TestCase):
    def test_direct_equipment_is_included(self):
        result = classify_tender_relevance(announcement("多功能事務機租賃案"))
        self.assertEqual(result["status"], "included")
        self.assertIn("多功能事務機", result["matched_terms"])

    def test_broad_title_waits_for_detail(self):
        result = classify_tender_relevance(announcement("辦公室設備更新採購案"))
        self.assertEqual(result["status"], "review")

    def test_procurement_word_alone_is_not_a_candidate(self):
        result = classify_tender_relevance(announcement("校舍修繕採購案"))
        self.assertEqual(result["status"], "excluded")

    def test_broad_title_can_be_confirmed_by_specification(self):
        result = classify_tender_relevance(
            announcement("辦公室設備更新採購案"),
            {"規格": "數位複合機，A3 彩色列印、掃描及自動送稿，每分鐘 30 張"}
        )
        self.assertEqual(result["status"], "included")
        self.assertIn("detail", result["matched_fields"])

    def test_machine_tool_is_excluded(self):
        result = classify_tender_relevance(announcement("CNC 車銑複合機採購案"))
        self.assertEqual(result["category"], "industrial_machine")

    def test_supplies_are_separated(self):
        result = classify_tender_relevance(announcement("影印機碳粉耗材採購"))
        self.assertEqual(result["category"], "supplies")

    def test_printing_service_is_not_equipment(self):
        result = classify_tender_relevance(announcement("年度文宣印製及海報輸出服務"))
        self.assertEqual(result["category"], "printing_service")

    def test_3d_printer_requires_separate_review(self):
        result = classify_tender_relevance(announcement("3D列印機乙項"))
        self.assertEqual(result["category"], "specialized_printing")
        self.assertEqual(result["status"], "review")


if __name__ == "__main__":
    unittest.main()
