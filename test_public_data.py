import unittest
import subprocess
from pathlib import Path

from scripts.export_public_data import export_public_data


class PublicDataTests(unittest.TestCase):
    def test_public_repository_does_not_track_private_state_or_old_bundles(self):
        root = Path(__file__).resolve().parent
        tracked = subprocess.check_output(["git", "ls-files"], cwd=root, text=True).splitlines()
        forbidden = [path for path in tracked if Path(path).name in {"subscribers.json", "sent_notifications.json"} or path.startswith((".private-state/", "assets/"))]
        self.assertEqual(forbidden, [])

    def test_internal_fields_never_cross_public_boundary(self):
        source = {
            "last_updated": "2026-11-07 08:48",
            "subscribers": [{"email": "private@example.test"}],
            "candidate_cache": [{"secret": "PRIVATE-CANARY"}],
            "history_cache": [{"secret": "PRIVATE-CANARY"}],
            "tenders": [{
                "title": "影印機租賃", "stage": "已決標", "main_competitor": "本公司 (互盛 RICOH)",
                "suggested_price": "PRIVATE-CANARY", "suggestion_basis": {"secret": "PRIVATE-CANARY"},
                "future_internal_field": "PRIVATE-CANARY",
                "relevance": {"category": "target_agency_procurement", "reason": "PRIVATE-CANARY"},
                "history_records": [{"winner": "公開廠商", "source_url": "https://web.pcc.gov.tw/notice", "private_note": "PRIVATE-CANARY"}],
            }],
            "forecasted_tenders": [{
                "unit": "公開機關", "incumbent": {"label": "PRIVATE-CANARY"}, "action_suggestion": "PRIVATE-CANARY",
                "current_status": {"status": "tender", "action_note": "PRIVATE-CANARY"},
            }],
            "collection_status": {"status": "complete", "private_note": "PRIVATE-CANARY"},
        }
        result = export_public_data(source)
        self.assertNotIn("PRIVATE-CANARY", str(result))
        self.assertNotIn("private@example.test", str(result))
        self.assertEqual(result["tenders"][0]["winner"], "互盛（RICOH）")
        self.assertEqual(result["tenders"][0]["relevance"]["category"], "target_agency_procurement")
        self.assertEqual(result["tenders"][0]["history_records"][0]["winner"], "公開廠商")
        self.assertEqual(export_public_data(result), result)

    def test_empty_datasets_remain_empty(self):
        self.assertEqual(export_public_data({"tenders": []})["tenders"], [])

    def test_unknown_nested_values_and_unsafe_links_are_not_published(self):
        result = export_public_data({"tenders": [{"title": {"email": "private@example.test"}, "tender_url": "javascript:alert(1)"}]})
        self.assertNotIn("title", result["tenders"][0])
        self.assertNotIn("tender_url", result["tenders"][0])

    def test_only_awards_publish_a_winner(self):
        result = export_public_data({"tenders": [{"stage": "無法決標", "main_competitor": "內部競品推估"}]})
        self.assertNotIn("winner", result["tenders"][0])

    def test_invalid_dataset_is_not_silently_published(self):
        with self.assertRaises(ValueError):
            export_public_data({"error": "upstream failed"})


if __name__ == "__main__":
    unittest.main()
