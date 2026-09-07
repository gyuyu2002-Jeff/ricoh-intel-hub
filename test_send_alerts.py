# -*- coding: utf-8 -*-
import unittest
from send_alerts import (
    generate_fingerprint,
    match_tenders_for_subscriber,
    build_email_html,
    build_welcome_email_html,
    send_welcome_email,
    is_allowed_domain,
    unsubscribe_email
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

    def test_category_matching_filters_correctly(self):
        tenders_with_streams = [
            {"job_number": "T1", "city": "台北市", "stream": "copier", "publish_date": "2026-09-05"},
            {"job_number": "T2", "city": "台北市", "stream": "peripherals", "publish_date": "2026-09-05"},
        ]
        # Only wants copier
        sub_copier = {"email": "copier@example.com", "cities": ["全部"], "categories": ["copier"]}
        m_copier = match_tenders_for_subscriber(sub_copier, tenders_with_streams, {})
        self.assertEqual(len(m_copier), 1)
        self.assertEqual(m_copier[0]["job_number"], "T1")

        # Only wants peripherals
        sub_periph = {"email": "periph@example.com", "cities": ["全部"], "categories": ["peripherals"]}
        m_periph = match_tenders_for_subscriber(sub_periph, tenders_with_streams, {})
        self.assertEqual(len(m_periph), 1)
        self.assertEqual(m_periph[0]["job_number"], "T2")

        # Wants both
        sub_both = {"email": "both@example.com", "cities": ["全部"], "categories": ["copier", "peripherals"]}
        m_both = match_tenders_for_subscriber(sub_both, tenders_with_streams, {})
        self.assertEqual(len(m_both), 2)

        # Subscriber selected '全台所有縣市'
        sub_all_tw = {"email": "user_tw@example.com", "cities": ["全台所有縣市"]}
        matching_all_tw = match_tenders_for_subscriber(sub_all_tw, self.sample_tenders, sent_logs={})
        self.assertEqual(len(matching_all_tw), 2)

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

    def test_build_welcome_email_html(self):
        html = build_welcome_email_html("newuser@example.com", ["桃園市", "台北市"], self.sample_tenders)
        self.assertIn("newuser@example.com", html)
        self.assertIn("桃園市、台北市", html)
        self.assertIn("互盛情報中樞 · 通知設定成功", html)
        self.assertIn("huxen.ricoh@gmail.com", html)
        self.assertIn("116-117年影印機租賃案", html)

    def test_send_welcome_email_dry_run(self):
        res = send_welcome_email("test_dry@example.com", cities=["全部"], dry_run=True)
        self.assertTrue(res)

    def test_domain_whitelisting(self):
        self.assertTrue(is_allowed_domain("hanjiunwu@eosasc.com.tw"))
        self.assertTrue(is_allowed_domain("huxen.ricoh@gmail.com"))
        self.assertTrue(is_allowed_domain("USER@GMAIL.COM"))
        # External or other domains must be blocked
        self.assertFalse(is_allowed_domain("attacker@yahoo.com"))
        self.assertFalse(is_allowed_domain("spammer@hotmail.com"))
        self.assertFalse(is_allowed_domain("unknown@ricoh.com.tw"))
        self.assertFalse(is_allowed_domain("invalid-email"))

    def test_unsubscribe_link_in_emails(self):
        alert_html = build_email_html("hanjiunwu@eosasc.com.tw", [self.sample_tenders[0]], "2026-09-05")
        self.assertIn("立即取消訂閱", alert_html)
        self.assertIn("action=unsubscribe", alert_html)
        self.assertIn("email=hanjiunwu%40eosasc.com.tw", alert_html)

        welcome_html = build_welcome_email_html("hanjiunwu@eosasc.com.tw", ["高雄市"])
        self.assertIn("立即取消訂閱", welcome_html)
        self.assertIn("action=unsubscribe", welcome_html)

        # Verify RFC 8058 List-Unsubscribe headers in SMTP message
        from send_alerts import create_email_message
        msg = create_email_message("hanjiunwu@eosasc.com.tw", "測試主旨", alert_html, "huxen.ricoh@gmail.com")
        self.assertIn("List-Unsubscribe", msg)
        self.assertIn("action=unsubscribe", msg["List-Unsubscribe"])
        self.assertEqual(msg["List-Unsubscribe-Post"], "List-Unsubscribe=One-Click")

    def test_forecast_matching_and_rendering(self):
        from send_alerts import generate_forecast_fingerprint, match_forecasts_for_subscriber

        sample_forecasts = [
            {
                "id": "forecast-A.7.6-影印機租賃-standard",
                "unit_id": "A.7.6",
                "unit": "財政部中區國稅局",
                "city": "台中市",
                "predicted_title": "115-116年本局及各稽徵所租賃影印機",
                "latest_title": "本局及各稽徵所租賃影印機69台",
                "latest_award_price_str": "NT$ 4,879,149",
                "latest_winner": "台灣佳能 (Canon)",
                "incumbent": {
                    "type": "competitor",
                    "label": "⚔️ 他牌進攻：台灣佳能 (Canon)"
                },
                "predicted_month": "2026年09月",
                "predicted_range": "2026年09月 ～ 10月",
                "days_until": 15,
                "countdown_label": "倒數 15 天",
                "cadence_summary": "歷史每 24 個月定期換約",
                "expansion": {
                    "has_extension": True,
                    "badge_label": "⚡ 含未來1年擴充 · 雙重提醒",
                    "notice": "原合約即將到期，若未擴充依法重招。"
                },
                "action_suggestion": "建議提早拜訪資訊組。"
            }
        ]

        # 1. Fingerprint is deterministic
        fp1 = generate_forecast_fingerprint("user@example.com", sample_forecasts[0])
        fp2 = generate_forecast_fingerprint("USER@EXAMPLE.COM ", sample_forecasts[0])
        self.assertEqual(fp1, fp2)
        self.assertIn("forecast", fp1)

        # 2. Matching with subscriber categories
        sub_forecast = {"email": "user@example.com", "cities": ["台中市"], "categories": ["forecast"]}
        matched = match_forecasts_for_subscriber(sub_forecast, sample_forecasts, sent_logs={})
        self.assertEqual(len(matched), 1)

        # Deduplication works for forecasts
        matched_dup = match_forecasts_for_subscriber(sub_forecast, sample_forecasts, sent_logs={fp1: True})
        self.assertEqual(len(matched_dup), 0)

        # City filter works for forecasts
        sub_other_city = {"email": "user@example.com", "cities": ["高雄市"], "categories": ["forecast"]}
        matched_other = match_forecasts_for_subscriber(sub_other_city, sample_forecasts, sent_logs={})
        self.assertEqual(len(matched_other), 0)

        # 3. HTML email rendering with both tenders and forecasts
        html = build_email_html("user@example.com", [self.sample_tenders[0]], "2026-09-06", forecasts=sample_forecasts)
        self.assertIn("本日最新公告與進行中案件", html)
        self.assertIn("推測未來上架案件 · 未來 6 個月換約預警", html)
        self.assertIn("115-116年本局及各稽徵所租賃影印機", html)
        self.assertIn("財政部中區國稅局", html)
        self.assertIn("台灣佳能", html)
        self.assertIn("擴充條款提醒", html)

    def test_forecast_closed_loop_solicitation_email_rendering(self):
        sample_solicitation_forecast = [
            {
                "id": "forecast-3.13.50.48.1-115117年度影印機租賃長約-standard",
                "unit_id": "3.13.50.48.1",
                "unit": "台灣中油股份有限公司煉製事業部桃園煉油廠",
                "city": "桃園市",
                "predicted_title": "115117年度影印機租賃長約",
                "latest_title": "112114年度影印機租賃長約",
                "latest_job_number": "I7312C021",
                "latest_source_url": "https://web.pcc.gov.tw/prkms/tender/common/notice/redirectShowNotice?file=PPW-3-50000000",
                "latest_award_price_str": "NT$ 6,500,000",
                "latest_winner": "互盛股份有限公司",
                "incumbent": {
                    "type": "us",
                    "label": "🛡️ 我方防守中：互盛 (Ricoh)"
                },
                "predicted_month": "2026年08月",
                "predicted_range": "2026年08月 ～ 09月",
                "days_until": -15,
                "countdown_label": "已逾預估期 15 天",
                "cadence_summary": "歷史每 36 個月定期換約",
                "current_status": {
                    "status": "solicitation",
                    "stage": "公開徵求",
                    "job_number": "I7315D063",
                    "title": "115117年度影印機租賃長約",
                    "date": "2026-08-10",
                    "notice_url": "https://web.pcc.gov.tw/prkms/tender/common/notice/redirectShowNotice?file=PPW-1-70112048",
                    "summary": "機關於 2026-08-10 發布「115117年度影印機租賃長約」公開徵求廠商提供參考資料（案號 I7315D063）"
                },
                "history_track": [
                    {
                        "date": "2023-11-20",
                        "title": "112114年度影印機租賃長約",
                        "job_number": "I7312C021",
                        "amount": 6500000,
                        "source_url": "https://web.pcc.gov.tw/prkms/tender/common/notice/redirectShowNotice?file=PPW-3-50000000"
                    }
                ],
                "expansion": {
                    "has_extension": False,
                    "badge_label": "常態期滿",
                    "notice": ""
                },
                "action_suggestion": "本案機關已啟動公開徵求廠商提供參考資料（案號 I7315D063），目前正處於規格與預算徵詢階段，請速提供理光新機型錄與效益方案。"
            }
        ]

        html = build_email_html("user@example.com", [], "2026-09-06", forecasts=sample_solicitation_forecast)
        self.assertIn("🔥 【本案已啟動招標前置：公開徵求中】", html)
        self.assertIn("🔥 公開徵求中", html)
        self.assertIn("查看本期公告 (公開徵求) ↗", html)
        self.assertIn("查看前次官方決標公告 ↗", html)
        self.assertIn("https://web.pcc.gov.tw/prkms/tender/common/notice/redirectShowNotice?file=PPW-1-70112048", html)
        self.assertIn("https://web.pcc.gov.tw/prkms/tender/common/notice/redirectShowNotice?file=PPW-3-50000000", html)
        self.assertIn("歷史開標履歷（可點擊查看各次決標）", html)

    def test_clean_and_count_rolling_deliveries(self):
        from send_alerts import clean_and_count_rolling_deliveries, log_email_delivery
        from datetime import datetime, timezone, timedelta

        now = datetime(2026, 9, 7, 12, 0, 0, tzinfo=timezone(timedelta(hours=8)))
        logs = {"_delivery_history": []}

        # 100 within last 2 hours
        for i in range(100):
            t = now - timedelta(hours=2, minutes=i)
            log_email_delivery(logs, f"user{i}@test.com", dry_run=False, now=t)

        # 50 within last 20 hours (total 150 in 24h)
        for i in range(50):
            t = now - timedelta(hours=20, minutes=i)
            log_email_delivery(logs, f"user_old{i}@test.com", dry_run=False, now=t)

        # 20 dry-run within last 2 hours (should NOT be counted in active quota)
        for i in range(20):
            t = now - timedelta(hours=1, minutes=i)
            log_email_delivery(logs, f"user_dry{i}@test.com", dry_run=True, now=t)

        # 30 between 25h and 40h ago (in 48h retention, but out of 24h quota)
        for i in range(30):
            t = now - timedelta(hours=35, minutes=i)
            log_email_delivery(logs, f"user_yesterday{i}@test.com", dry_run=False, now=t)

        # 10 older than 50 hours (should be pruned)
        for i in range(10):
            t = now - timedelta(hours=55, minutes=i)
            log_email_delivery(logs, f"ancient{i}@test.com", dry_run=False, now=t)

        count_24h, oldest_in_24h = clean_and_count_rolling_deliveries(logs, now=now)
        self.assertEqual(count_24h, 150)
        self.assertIsNotNone(oldest_in_24h)
        # History retained should be 100 + 50 + 20 + 30 = 200 (10 pruned)
        self.assertEqual(len(logs["_delivery_history"]), 200)

    def test_build_quota_alert_email_html_levels(self):
        from send_alerts import build_quota_alert_email_html
        from datetime import datetime, timezone, timedelta

        oldest = datetime(2026, 9, 7, 2, 30, 0, tzinfo=timezone(timedelta(hours=8)))

        # 1. Warning level
        html_warn = build_quota_alert_email_html("gyuyu2002@gmail.com", 410, 500, "warning", oldest_ts=oldest, subscriber_count=5)
        self.assertIn("gyuyu2002@gmail.com", html_warn)
        self.assertIn("410 / 500", html_warn)
        self.assertIn("82.0%", html_warn)
        self.assertIn("警戒", html_warn)
        self.assertIn("02:30", html_warn)

        # 2. Critical level
        html_crit = build_quota_alert_email_html("gyuyu2002@gmail.com", 460, 500, "critical", oldest_ts=oldest, subscriber_count=5)
        self.assertIn("高危", html_crit)
        self.assertIn("92.0%", html_crit)

        # 3. Circuit breaker level
        html_circuit = build_quota_alert_email_html("gyuyu2002@gmail.com", 488, 500, "circuit_breaker", oldest_ts=oldest, subscriber_count=5)
        self.assertIn("熔斷", html_circuit)
        self.assertIn("97.6%", html_circuit)
        self.assertIn("主動暫停", html_circuit)

    def test_check_and_alert_quota_escalation_and_throttling(self):
        from send_alerts import (
            check_and_alert_quota,
            log_email_delivery,
            GMAIL_DAILY_LIMIT,
            QUOTA_WARN_THRESHOLD,
            QUOTA_CRITICAL_THRESHOLD,
            QUOTA_CIRCUIT_BREAKER
        )
        from datetime import datetime, timezone, timedelta

        now = datetime(2026, 9, 7, 10, 0, 0, tzinfo=timezone(timedelta(hours=8)))
        logs = {"_delivery_history": []}

        # 1. Below threshold: 350 emails -> Normal, no alert
        for i in range(350):
            log_email_delivery(logs, f"u{i}@test.com", now=now - timedelta(hours=1))
        alerted, level, count = check_and_alert_quota(logs, dry_run=True, now=now)
        self.assertFalse(alerted)
        self.assertEqual(level, "normal")
        self.assertEqual(count, 350)

        # 2. Reaches 405 (>= 400 Warning) -> Alert triggered
        for i in range(55):
            log_email_delivery(logs, f"u_warn{i}@test.com", now=now - timedelta(minutes=30))
        alerted, level, count = check_and_alert_quota(logs, dry_run=True, now=now)
        self.assertTrue(alerted)
        self.assertEqual(level, "warning")
        self.assertEqual(count, 405)

        # 3. Same level 1 hour later (410 emails) -> Throttled by 12h cooldown
        log_email_delivery(logs, "u_more@test.com", now=now + timedelta(hours=1))
        alerted_throttle, level_throttle, count_throttle = check_and_alert_quota(
            logs, dry_run=True, now=now + timedelta(hours=1)
        )
        self.assertFalse(alerted_throttle)
        self.assertEqual(level_throttle, "warning")

        # 4. Severity escalation to Critical (455 emails >= 450) -> Must trigger despite cooldown!
        for i in range(45):
            log_email_delivery(logs, f"u_crit{i}@test.com", now=now + timedelta(hours=1, minutes=10))
        alerted_escalate, level_escalate, count_escalate = check_and_alert_quota(
            logs, dry_run=True, now=now + timedelta(hours=1, minutes=15)
        )
        self.assertTrue(alerted_escalate)
        self.assertEqual(level_escalate, "critical")
        self.assertGreaterEqual(count_escalate, 450)

        # 5. Severity escalation to Circuit Breaker (490 emails >= 485) -> Must trigger!
        for i in range(40):
            log_email_delivery(logs, f"u_circuit{i}@test.com", now=now + timedelta(hours=1, minutes=20))
        alerted_cb, level_cb, count_cb = check_and_alert_quota(
            logs, dry_run=True, now=now + timedelta(hours=1, minutes=25)
        )
        self.assertTrue(alerted_cb)
        self.assertEqual(level_cb, "circuit_breaker")
        self.assertGreaterEqual(count_cb, 485)

    def test_circuit_breaker_halts_dispatch(self):
        from send_alerts import (
            dispatch_alerts,
            log_email_delivery,
            save_json_file,
            load_json_file,
            SENT_LOG_FILE,
            QUOTA_CIRCUIT_BREAKER
        )
        from datetime import datetime, timezone, timedelta

        # Setup sent_notifications with 490 sends (exceeds circuit breaker 485)
        now = datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=8)))
        test_logs = {"_delivery_history": []}
        for i in range(QUOTA_CIRCUIT_BREAKER + 5):
            log_email_delivery(test_logs, f"user{i}@test.com", now=now - timedelta(minutes=10))

        backup = load_json_file(SENT_LOG_FILE, default_val={})
        try:
            save_json_file(SENT_LOG_FILE, test_logs)
            dispatched = dispatch_alerts(dry_run=True)
            # Circuit breaker must halt and notify 0 subscribers
            self.assertEqual(dispatched, 0)
        finally:
            save_json_file(SENT_LOG_FILE, backup)


if __name__ == "__main__":
    unittest.main()


