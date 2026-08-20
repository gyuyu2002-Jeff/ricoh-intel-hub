import unittest
from datetime import date, timedelta

from update_tenders import (
    build_required_dates,
    classify_tender_relevance,
    deduplicate_announcements,
    get_city_info,
    is_past_deadline,
    is_failed_notice,
    is_award_notice,
    resolve_notice_status,
    extract_dates,
)


def announcement(title, category=""):
    return {"brief": {"title": title, "category": category}}


class DeadlineRetentionTests(unittest.TestCase):
    def test_expired_tender_is_not_active(self):
        self.assertTrue(is_past_deadline("2026-07-16", date(2026, 8, 20)))

    def test_today_deadline_remains_active(self):
        self.assertFalse(is_past_deadline("2026-08-20", date(2026, 8, 20)))

    def test_unknown_deadline_is_not_assumed_expired(self):
        self.assertFalse(is_past_deadline("未公開", date(2026, 8, 20)))


class StatusAndDateConfidenceTests(unittest.TestCase):
    def test_failed_status_variants_are_detected(self):
        for phrase in ["流標", "廢標", "未達法定家數", "無廠商投標", "無人投標", "不予開標", "撤標", "撤案", "停止採購", "取消採購"]:
            with self.subTest(phrase=phrase):
                self.assertTrue(is_failed_notice({"brief": {"type": phrase}}))

    def test_failed_status_can_be_found_in_detail_value(self):
        self.assertTrue(is_failed_notice({"brief": {}, "detail": {"開標結果": "本案無廠商投標，流標"}}))

    def test_award_wins_over_failed_notice(self):
        records = [
            {"brief": {"type": "廢標"}},
            {"brief": {"type": "決標公告"}, "detail": {"得標廠商": "測試公司"}},
        ]
        self.assertEqual(resolve_notice_status(records), "已決標")

    def test_failed_status_wins_when_no_award_exists(self):
        self.assertEqual(resolve_notice_status([{"brief": {"type": "撤案公告"}}]), "無法決標")

    def test_verified_dates_are_marked_verified(self):
        result = extract_dates({"公告日期": "115/08/20", "截止投標": "115/08/27"}, "20260820")
        self.assertEqual(result, ("2026-08-20", "2026-08-27", "verified", "verified"))

    def test_publish_fallback_and_deadline_are_marked_inferred(self):
        result = extract_dates({}, "20260820")
        self.assertEqual(result, ("2026-08-20", "2026-09-03", "inferred", "inferred"))

    def test_invalid_dates_remain_unknown(self):
        result = extract_dates({"公告日期": "日期待確認", "截止投標": "尚未公告"}, "bad-date")
        self.assertEqual(result, ("", "", "unknown", "unknown"))


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

    def test_3d_printer_is_excluded(self):
        result = classify_tender_relevance(announcement("3D列印機乙項"))
        self.assertEqual(result["category"], "specialized_printing")
        self.assertEqual(result["status"], "excluded")

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

    def test_contact_fax_does_not_confirm_broad_equipment(self):
        result = classify_tender_relevance(
            announcement("資訊設備採購案"),
            {"機關資料:傳真號碼": "02-12345678", "其他:申訴受理單位": "電話及傳真"}
        )
        self.assertEqual(result["status"], "review")
        self.assertNotIn("傳真", result["matched_terms"])

    def test_network_equipment_is_excluded(self):
        result = classify_tender_relevance(announcement("無線網路資訊設備壹式"))
        self.assertEqual(result["status"], "excluded")
        self.assertEqual(result["category"], "network_or_server")

    def test_medical_equipment_is_excluded(self):
        result = classify_tender_relevance(announcement("衛生所辦公設備—智慧藥櫃"))
        self.assertEqual(result["status"], "excluded")
        self.assertEqual(result["category"], "medical_equipment")

    def test_explicit_printer_in_mixed_it_purchase_is_excluded(self):
        result = classify_tender_relevance(announcement("電腦及雷射印表機採購案"))
        self.assertEqual(result["status"], "excluded")
        self.assertEqual(result["category"], "printer_or_plotter")

    def test_plotter_is_excluded(self):
        result = classify_tender_relevance(announcement("大型繪圖機採購案"))
        self.assertEqual(result["status"], "excluded")
        self.assertEqual(result["category"], "printer_or_plotter")

    def test_copier_and_printer_mixed_purchase_remains_in_scope(self):
        result = classify_tender_relevance(announcement("數位複合機及印表機採購案"))
        self.assertEqual(result["status"], "included")

    def test_contract_change_is_excluded(self):
        result = classify_tender_relevance(announcement("影印機租賃契約變更"))
        self.assertEqual(result["status"], "excluded")
        self.assertEqual(result["category"], "contract_change")

    def test_duplicate_corrections_keep_newest_announcement(self):
        records = [
            {"unit_id": "1", "job_number": "A", "date": "20260728", "filename": "old"},
            {"unit_id": "1", "job_number": "A", "date": "20260729", "filename": "new"},
        ]
        result = deduplicate_announcements(records)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["filename"], "new")


class CityClassificationTests(unittest.TestCase):
    def test_county_from_unit_name_is_preserved(self):
        result = get_city_info("花蓮縣政府")
        self.assertEqual(result["city"], "花蓮縣")
        self.assertEqual(result["city_source"], "機關名稱")
        self.assertEqual(result["city_confidence"], "high")

    def test_city_from_execution_location_is_high_confidence(self):
        result = get_city_info(
            "某地方機關",
            {"records": [{"detail": {"履約地點": "嘉義市東區"}}]}
        )
        self.assertEqual(result["city"], "嘉義市")
        self.assertEqual(result["city_source"], "履約地點")

    def test_unknown_unit_is_not_silently_assigned_to_taipei(self):
        result = get_city_info("某某地方機關")
        self.assertEqual(result["city"], "未分類")
        self.assertEqual(result["city_confidence"], "low")


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
