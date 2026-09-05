# -*- coding: utf-8 -*-
import unittest
from send_alerts import (
    generate_fingerprint,
    match_tenders_for_subscriber,
    build_email_html
)


class TestSendAlerts(unittest.TestCase):
    def setUp(self):
        self.sample_tenders = [
            {
                "job_number": "CGS115-01",
                "title": "116-117年影印機租賃案",
                "city": "高雄市",
                "stage": "公開徵求價單",
                "publish_date": "2026-09-04",
                "deadline": "2026-09-08",
                "budget": "NT$ 800,000",
                "suggested_price": "NT$ 665,000",
                "avg_discount": "83.2%",
                "main_competitor": "震旦 SHARP",
                "tender_url": "https://web.pcc.gov.tw/cgs"
            },
            {
                "job_number": "TY115-001",
                "title": "115年度多功能複合機租賃",
                "city": "桃園市",
                "stage": "正式開標",
                "publish_date": "2026-09-03",
                "deadline": "2026-09-17",
                "budget": "NT$ 1,200,000",
                "suggested_price": "NT$ 980,000",
                "avg_discount": "81.6%",
                "main_competitor": "宏羚",
                "tender_url": "https://web.pcc.gov.tw/ty"
            }
        ]

    def test_generate_fingerprint_is_deterministic(self):
        fp1 = generate_fingerprint("test@example.com", self.sample_tenders[0])
        fp2 = generate_fingerprint("TEST@EXAMPLE.COM ", self.sample_tenders[0])
        self.assertEqual(fp1, fp2)
        self.assertIn("cgs115-01", fp1.lower())

    def test_city_matching_filters_correctly(self):
        # Subscriber only wants 桃園市
        sub_ty = {"email": "user_ty@example.com", "cities": ["桃園市"]}
        matching = match_tenders_for_subscriber(sub_ty, self.sample_tenders, sent_logs={})
        self.assertEqual(len(matching), 1)
        self.assertEqual(matching[0]["job_number"], "TY115-001")

        # Subscriber wants all cities
        sub_all = {"email": "user_all@example.com", "cities": ["全部"]}
        matching_all = match_tenders_for_subscriber(sub_all, self.sample_tenders, sent_logs={})
        self.assertEqual(len(matching_all), 2)

    def test_deduplication_prevents_re_sending(self):
        sub = {"email": "user@example.com", "cities": ["高雄市"]}
        fp = generate_fingerprint("user@example.com", self.sample_tenders[0])
        sent_logs = {fp: {"sent_at": "2026-09-04 10:00:00"}}

        matching = match_tenders_for_subscriber(sub, self.sample_tenders, sent_logs=sent_logs)
        self.assertEqual(len(matching), 0)

    def test_build_email_html_structure(self):
        html = build_email_html("test@example.com", [self.sample_tenders[0]], "2026-09-05")
        self.assertIn("116-117年影印機租賃案", html)
        self.assertIn("NT$ 800,000", html)
        self.assertIn("公開徵求", html)
        self.assertIn("https://web.pcc.gov.tw/cgs", html)
        self.assertIn("huxen.ricoh@gmail.com", html)


if __name__ == "__main__":
    unittest.main()
