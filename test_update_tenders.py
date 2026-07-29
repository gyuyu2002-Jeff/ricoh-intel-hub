import unittest
from datetime import date, timedelta

from update_tenders import build_required_dates, classify_tender_relevance


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


class TenderRelevanceAdditionalTests(unittest.TestCase):
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

    def test_dot_matrix_printer_is_excluded(self):
        result = classify_tender_relevance(announcement("點陣式印表機汰換"))
        self.assertEqual(result["category"], "dot_matrix_printer")
        self.assertEqual(result["status"], "excluded")

    def test_printer_maintenance_is_excluded(self):
        result = classify_tender_relevance(announcement("115年度個人電腦及印表機設備維護工作"))
        self.assertEqual(result["category"], "printer_maintenance")
        self.assertEqual(result["status"], "excluded")

    def test_copier_maintenance_remains_in_scope(self):
        result = classify_tender_relevance(announcement("數位影印機維護案"))
        self.assertEqual(result["status"], "included")


class UpdateModeTests(unittest.TestCase):
    def test_live_mode_only_fetches_today_and_yesterday(self):
        today = date(2026, 7, 28)
        self.assertEqual(
            build_required_dates("live", today, {}),
            [today, today - timedelta(days=1)]
        )

    def test_maintenance_mode_fetches_one_missing_backfill_day(self):
        today = date(2026, 7, 28)
        collection_days = {
            "2026-07-26": {"status": "complete"},
            "2026-07-25": {"status": "incomplete"}
        }
        self.assertEqual(
            build_required_dates("maintenance", today, collection_days),
            [date(2026, 7, 25)]
        )


if __name__ == "__main__":
    unittest.main()
