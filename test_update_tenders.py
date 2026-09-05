import unittest
from datetime import date, timedelta

from update_tenders import (
    build_required_dates,
    build_history_title_query,
    classify_tender_relevance,
    deduplicate_announcements,
    get_city_info,
    is_past_deadline,
    is_failed_notice,
    is_award_notice,
    resolve_notice_status,
    extract_dates,
    is_terminal_notice_type,
    review_city_fields,
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

    def test_award_method_in_live_notice_is_not_an_award(self):
        live_notice = {
            "brief": {"type": "公開取得報價單或企劃書公告"},
            "detail": {
                "招標資料:決標方式": "參考最有利標精神",
                "領投開標:截止投標": "115/09/01 09:30",
            },
        }
        self.assertFalse(is_award_notice(live_notice))
        self.assertEqual(resolve_notice_status([live_notice]), "")

    def test_populated_award_result_detail_is_an_award(self):
        award_notice = {"brief": {}, "detail": {"決標結果:得標廠商": "測試公司"}}
        self.assertTrue(is_award_notice(award_notice))

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
        self.assertEqual(result["status"], "excluded")
        self.assertEqual(result["category"], "broad_office_equipment")


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
        self.assertEqual(result["stream"], "peripherals")
        self.assertEqual(result["status"], "included")

    def test_copier_rental_including_supplies_is_included(self):
        result = classify_tender_relevance(announcement("116-117年影印機(含安裝、運費、維修、耗材等計張費用)租賃案"))
        self.assertEqual(result["category"], "office_output_equipment")
        self.assertEqual(result["stream"], "copier")
        self.assertEqual(result["status"], "included")

    def test_printing_service_is_not_equipment(self):
        result = classify_tender_relevance(announcement("年度文宣印製及海報輸出服務"))
        self.assertEqual(result["category"], "printing_service")

    def test_3d_printer_is_excluded(self):
        result = classify_tender_relevance(announcement("3D列印機乙項"))
        self.assertEqual(result["category"], "specialized_printing")
        self.assertEqual(result["status"], "excluded")

    def test_dot_matrix_printer_is_included_in_peripherals(self):
        result = classify_tender_relevance(announcement("點陣式印表機汰換"))
        self.assertEqual(result["category"], "dot_matrix_printer")
        self.assertEqual(result["stream"], "peripherals")
        self.assertEqual(result["status"], "included")

    def test_printer_maintenance_is_excluded(self):
        result = classify_tender_relevance(announcement("115年度個人電腦及印表機設備維護工作"))
        self.assertEqual(result["status"], "excluded")

    def test_copier_maintenance_remains_in_scope(self):
        result = classify_tender_relevance(announcement("數位影印機維護案"))
        self.assertEqual(result["status"], "included")

    def test_information_equipment_is_always_excluded_even_with_contact_fax(self):
        result = classify_tender_relevance(
            announcement("資訊設備採購案"),
            {"機關資料:傳真號碼": "02-12345678", "其他:申訴受理單位": "電話及傳真"}
        )
        self.assertEqual(result["status"], "excluded")
        self.assertEqual(result["category"], "information_equipment")
        self.assertIn("資訊設備", result["matched_terms"])

    def test_network_equipment_is_excluded(self):
        result = classify_tender_relevance(announcement("無線網路資訊設備壹式"))
        self.assertEqual(result["status"], "excluded")
        self.assertEqual(result["category"], "information_equipment")

    def test_information_equipment_overrides_copier_keyword(self):
        result = classify_tender_relevance(announcement("資訊設備及影印機採購案"))
        self.assertEqual(result["status"], "excluded")
        self.assertEqual(result["category"], "information_equipment")

    def test_flooring_overrides_copier_keyword(self):
        result = classify_tender_relevance(announcement("影印機租賃及辦公室地板更新工程"))
        self.assertEqual(result["status"], "excluded")
        self.assertEqual(result["category"], "construction_or_furniture")

    def test_construction_overrides_copier_keyword(self):
        result = classify_tender_relevance(announcement("多功能事務機採購暨室內裝修工程"))
        self.assertEqual(result["status"], "excluded")
        self.assertEqual(result["category"], "construction_or_furniture")

    def test_relocation_overrides_copier_keyword(self):
        result = classify_tender_relevance(announcement("影印機搬遷及辦公設備整備案"))
        self.assertEqual(result["status"], "excluded")
        self.assertEqual(result["category"], "non_pure_scope")

    def test_scrap_sale_overrides_copier_keyword(self):
        result = classify_tender_relevance(announcement("報廢影印機及事務設備財物標售案"))
        self.assertEqual(result["status"], "excluded")
        self.assertEqual(result["category"], "non_pure_scope")

    def test_system_integration_overrides_copier_keyword(self):
        result = classify_tender_relevance(announcement("多功能事務機及系統整合採購案"))
        self.assertEqual(result["status"], "excluded")
        self.assertEqual(result["category"], "non_pure_scope")

    def test_broad_office_equipment_without_copier_is_excluded(self):
        result = classify_tender_relevance(announcement("多功能辦公室設備採購案"))
        self.assertEqual(result["status"], "excluded")
        self.assertEqual(result["category"], "broad_office_equipment")

    def test_copier_rental_with_floor_number_remains_in_scope(self):
        result = classify_tender_relevance(announcement("一樓行政室數位影印機租賃案"))
        self.assertEqual(result["status"], "included")

    def test_surveillance_equipment_overrides_copier_keyword(self):
        result = classify_tender_relevance(announcement("監視器及影印機採購案"))
        self.assertEqual(result["status"], "excluded")
        self.assertEqual(result["category"], "surveillance_access")

    def test_access_control_system_is_excluded(self):
        result = classify_tender_relevance(announcement("新廳舍門禁系統及人臉辨識設備採購"))
        self.assertEqual(result["status"], "excluded")
        self.assertEqual(result["category"], "surveillance_access")

    def test_network_endpoint_is_excluded(self):
        result = classify_tender_relevance(announcement("無線基地台、網路交換器及伺服器採購案"))
        self.assertEqual(result["status"], "excluded")
        self.assertEqual(result["category"], "network_or_server")

    def test_display_equipment_is_excluded(self):
        result = classify_tender_relevance(announcement("互動式顯示器及電子白板採購案"))
        self.assertEqual(result["status"], "excluded")
        self.assertEqual(result["category"], "it_endpoint")

    def test_copier_only_remains_in_scope_after_information_exclusion(self):
        result = classify_tender_relevance(announcement("數位影印機租賃案"))
        self.assertEqual(result["status"], "included")

    def test_network_printing_feature_does_not_exclude_copier(self):
        result = classify_tender_relevance(announcement("具網路列印與掃描功能之多功能事務機租賃案"))
        self.assertEqual(result["status"], "included")

    def test_medical_equipment_is_excluded(self):
        result = classify_tender_relevance(announcement("衛生所辦公設備—智慧藥櫃"))
        self.assertEqual(result["status"], "excluded")
        self.assertEqual(result["category"], "medical_equipment")

    def test_explicit_printer_in_mixed_it_purchase_is_excluded(self):
        result = classify_tender_relevance(announcement("電腦及雷射印表機採購案"))
        self.assertEqual(result["status"], "excluded")

    def test_plotter_is_included_in_peripherals(self):
        result = classify_tender_relevance(announcement("大型繪圖機採購案"))
        self.assertEqual(result["status"], "included")
        self.assertEqual(result["stream"], "peripherals")
        self.assertEqual(result["sub_type"], "printer")

    def test_scanner_is_included_in_peripherals(self):
        result = classify_tender_relevance(announcement("高速雙面文件掃描器採購案"))
        self.assertEqual(result["status"], "included")
        self.assertEqual(result["stream"], "peripherals")
        self.assertEqual(result["sub_type"], "scanner")

    def test_office_sundry_is_excluded(self):
        result = classify_tender_relevance(announcement("公務用碎紙機採購案"))
        self.assertEqual(result["status"], "excluded")
        self.assertEqual(result["category"], "office_sundry")

    def test_binding_machine_is_excluded(self):
        result = classify_tender_relevance(announcement("電動打孔裝訂機採購案"))
        self.assertEqual(result["status"], "excluded")
        self.assertEqual(result["category"], "office_sundry")

    def test_laminator_is_excluded(self):
        result = classify_tender_relevance(announcement("辦公室護貝機採購案"))
        self.assertEqual(result["status"], "excluded")
        self.assertEqual(result["category"], "office_sundry")

    def test_copier_and_printer_mixed_purchase_remains_in_scope(self):
        result = classify_tender_relevance(announcement("數位複合機及印表機採購案"))
        self.assertEqual(result["status"], "included")
        self.assertEqual(result["stream"], "copier")

    def test_mutual_exclusion_between_streams(self):
        cases = [
            ("多功能複合機租賃案", "copier"),
            ("數位影印機採購", "copier"),
            ("影印機碳粉耗材採購", "peripherals"),
            ("A4彩色雷射印表機採購", "peripherals"),
            ("高速文件掃描儀採購", "peripherals"),
            ("點陣式印表機汰換", "peripherals"),
        ]
        for title, expected_stream in cases:
            res = classify_tender_relevance(announcement(title))
            self.assertEqual(res["status"], "included")
            self.assertEqual(res["stream"], expected_stream)

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

    def test_terminal_variants_are_filtered_before_active_processing(self):
        for phrase in ["流標公告", "廢標公告", "撤案公告", "無廠商投標結果", "決標公告"]:
            with self.subTest(phrase=phrase):
                self.assertTrue(is_terminal_notice_type(phrase))

    def test_full_lifecycle_keeps_active_and_terminal_buckets_separate(self):
        records = [
            {"unit_id": "1", "job_number": "A", "date": "20260801", "filename": "active", "brief": {"type": "招標公告"}},
            {"unit_id": "1", "job_number": "A", "date": "20260802", "filename": "failed", "brief": {"type": "流標公告"}},
            {"unit_id": "1", "job_number": "A", "date": "20260803", "filename": "rebid", "brief": {"type": "重新招標公告"}},
            {"unit_id": "1", "job_number": "A", "date": "20260804", "filename": "award", "brief": {"type": "決標公告"}},
        ]
        result = deduplicate_announcements(records)
        self.assertEqual({row["filename"] for row in result}, {"rebid", "award"})


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

    def test_all_22_counties_and_cities_are_resolvable(self):
        cities = ["台北市", "新北市", "桃園市", "台中市", "台南市", "高雄市", "基隆市", "新竹市", "嘉義市", "新竹縣", "苗栗縣", "彰化縣", "南投縣", "雲林縣", "嘉義縣", "屏東縣", "宜蘭縣", "花蓮縣", "台東縣", "澎湖縣", "金門縣", "連江縣"]
        for city in cities:
            with self.subTest(city=city):
                self.assertEqual(get_city_info(f"{city}政府")["city"], city)

    def test_review_city_fields_preserve_location_evidence(self):
        result = review_city_fields("某地方機關", {"records": [{"detail": {"履約地點": "花蓮縣壽豐鄉"}}]})
        self.assertEqual(result["city"], "花蓮縣")
        self.assertEqual(result["city_source"], "履約地點")
        self.assertEqual(result["city_confidence"], "high")
        self.assertIn("花蓮縣", result["city_raw_text"])


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

    def test_backfill_days_returns_explicit_range(self):
        today = date(2026, 7, 28)
        collection_days = {}
        self.assertEqual(
            build_required_dates("live", today, collection_days, backfill_days=3),
            [date(2026, 7, 28), date(2026, 7, 27), date(2026, 7, 26)]
        )


class HistoryTitleQueryTests(unittest.TestCase):
    def test_roc_year_prefix_is_removed_for_history_search(self):
        self.assertEqual(
            build_history_title_query("115年SHARP影印機計張維護開口契約"),
            "SHARP影印機計張維護開口契約",
        )

    def test_roc_year_and_yearly_suffix_are_removed_for_history_search(self):
        self.assertEqual(
            build_history_title_query("115年度 SHARP影印機計張維護開口契約"),
            "SHARP影印機計張維護開口契約",
        )


if __name__ == "__main__":
    unittest.main()
