# -*- coding: utf-8 -*-
"""
send_alerts.py - Automated Email Dispatcher for Ricoh Intel Hub
==============================================================
Reads newly identified tenders from data.json, matches against subscriber
city preferences, deduplicates using sent_notifications.json, and dispatches
professional HTML digest emails via Gmail SMTP.
"""

import os
import sys
import json
import smtplib
import argparse
import urllib.request
import urllib.parse
from datetime import datetime, timezone, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(SCRIPT_DIR, "data.json")
SENT_LOG_FILE = os.path.join(SCRIPT_DIR, "sent_notifications.json")
SUBSCRIBERS_FILE = os.path.join(SCRIPT_DIR, "subscribers.json")

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587


def load_json_file(filepath, default_val=None):
    if default_val is None:
        default_val = {}
    if not os.path.exists(filepath):
        return default_val
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Warning: Failed to load {filepath}: {e}")
        return default_val


def save_json_file(filepath, data):
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_subscribers():
    """
    Fetch subscriber list.
    Prioritizes remote Google Apps Script / Sheet API if SUBSCRIBERS_URL is set,
    otherwise falls back to local subscribers.json.
    """
    remote_url = os.environ.get("SUBSCRIBERS_URL", "").strip()
    if remote_url:
        try:
            req = urllib.request.Request(
                remote_url,
                headers={"User-Agent": "RicohIntelHub/1.0", "Accept": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if isinstance(data, list):
                    return data
                if isinstance(data, dict) and "subscribers" in data:
                    return data["subscribers"]
        except Exception as e:
            print(f"Notice: Failed to fetch remote subscribers ({e}). Falling back to local file.")

    local_data = load_json_file(SUBSCRIBERS_FILE, default_val=[])
    if isinstance(local_data, list):
        return local_data
    if isinstance(local_data, dict):
        return local_data.get("subscribers", [])
    return []


def generate_fingerprint(email, tender):
    """
    Create an immutable unique key for a notification to guarantee idempotency.
    Key structure: email : job_number : stage : publish_date
    """
    job = tender.get("job_number", "unknown")
    stage = tender.get("stage", "unknown")
    pub = tender.get("publish_date", "unknown")
    norm_email = email.strip().lower()
    return f"{norm_email}_{job}_{stage}_{pub}"


def match_tenders_for_subscriber(subscriber, tenders, sent_logs):
    """
    Filters tenders matching subscriber's cities that have not been sent yet.
    """
    norm_email = subscriber.get("email", "").strip().lower()
    if not norm_email or "@" not in norm_email:
        return []

    subscribed_cities = subscriber.get("cities", [])
    if isinstance(subscribed_cities, str):
        subscribed_cities = [c.strip() for c in subscribed_cities.split(",") if c.strip()]

    # '全部' or empty means all cities
    is_all_cities = not subscribed_cities or any(
        c in ["全部", "全部縣市", "全台", "全台所有縣市", "ALL"] for c in subscribed_cities
    )

    matching = []
    for tender in tenders:
        city = tender.get("city", "")
        if not is_all_cities and city not in subscribed_cities:
            continue

        fingerprint = generate_fingerprint(norm_email, tender)
        if fingerprint in sent_logs:
            continue

        matching.append(tender)

    return matching


def build_email_html(subscriber_email, tenders, taipei_date_str):
    """
    Builds a Neo-Editorial HTML email matching the Ricoh Intel Hub theme.
    """
    items_html = ""
    for t in tenders:
        is_solicitation = "公開徵求" in t.get("stage", "") or "徵求" in t.get("stage", "")
        stage_badge_bg = "#fff3cd" if is_solicitation else "#e8f4fd"
        stage_badge_color = "#856404" if is_solicitation else "#0c5460"
        stage_text = "📢 公開徵求價單／企劃" if is_solicitation else t.get("stage", "標案公告")

        budget_val = t.get("budget", "無公開數據")
        suggested_val = t.get("suggested_price", "資料不足")
        discount_val = t.get("avg_discount", "資料不足")
        winner_val = t.get("main_competitor", "尚無數據")
        tender_url = t.get("tender_url", "https://web.pcc.gov.tw/")

        items_html += f"""
        <div style="background:#ffffff; border:1px solid #d4ded7; border-left:4px solid #c92d3f; border-radius:8px; padding:18px 20px; margin-bottom:16px; box-shadow:0 2px 8px rgba(0,0,0,0.03);">
          <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px; flex-wrap:wrap;">
            <div>
              <span style="display:inline-block; background:#edf4ef; color:#2f5146; font-size:11px; font-weight:700; padding:3px 8px; border-radius:4px; margin-right:6px;">{t.get('city', '未知縣市')}</span>
              <span style="display:inline-block; background:{stage_badge_bg}; color:{stage_badge_color}; font-size:11px; font-weight:700; padding:3px 8px; border-radius:4px;">{stage_text}</span>
            </div>
            <span style="font-size:12px; color:#78857d; font-family:monospace;">案號 {t.get('job_number', '待查')}</span>
          </div>

          <h3 style="margin:6px 0 10px; font-size:16px; color:#202825; line-height:1.4;">
            <a href="{tender_url}" target="_blank" style="color:#202825; text-decoration:none; font-weight:700;">{t.get('title', '未命名標案')}</a>
          </h3>

          <div style="font-size:12px; color:#53605a; margin-bottom:12px;">
            <strong>發包機關：</strong>{t.get('unit', '機關待確認')} · <strong>公告日期：</strong>{t.get('publish_date', '待查')} · <strong>截止收件：</strong><span style="color:#c92d3f; font-weight:700;">{t.get('deadline', '待確認')}</span>
          </div>

          <table style="width:100%; border-collapse:collapse; background:#fbfcf8; border:1px solid #e2ece4; border-radius:6px; margin-bottom:12px; font-size:12px;">
            <tr>
              <td style="padding:8px 12px; border-right:1px solid #e2ece4; width:33%;">
                <div style="color:#8a968f; font-size:10px;">預算金額</div>
                <div style="color:#202825; font-weight:700; font-size:14px; margin-top:2px;">{budget_val}</div>
              </td>
              <td style="padding:8px 12px; border-right:1px solid #e2ece4; width:33%;">
                <div style="color:#8a968f; font-size:10px;">歷史折率中位數</div>
                <div style="color:#202825; font-weight:700; font-size:14px; margin-top:2px;">{discount_val}</div>
              </td>
              <td style="padding:8px 12px; width:34%;">
                <div style="color:#8a968f; font-size:10px;">推估行情參考價</div>
                <div style="color:#c92d3f; font-weight:700; font-size:14px; margin-top:2px;">{suggested_val}</div>
              </td>
            </tr>
          </table>

          <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px;">
            <span style="font-size:11px; color:#78857d;">前次/優勢廠商：<strong>{winner_val}</strong></span>
            <a href="{tender_url}" target="_blank" style="display:inline-block; background:#c92d3f; color:#ffffff; font-size:11px; font-weight:700; padding:6px 12px; border-radius:4px; text-decoration:none;">查看採購網官方公告 ↗</a>
          </div>
        </div>
        """

    html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>互盛情報中樞 - 今日標案通報</title>
</head>
<body style="margin:0; padding:24px 12px; background:#eef3ed; font-family:'Noto Sans TC', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; color:#202825;">
  <div style="max-width:680px; margin:0 auto; background:#fbfcf8; border:1px solid #d4ded7; border-radius:12px; overflow:hidden; box-shadow:0 8px 30px rgba(38,61,52,0.06);">
    <!-- Header -->
    <div style="background:#202825; color:#ffffff; padding:24px 28px; border-bottom:3px solid #c92d3f;">
      <div style="font-size:10px; font-weight:700; letter-spacing:0.12em; color:#a3b2a8; text-transform:uppercase;">RICOH INTERNAL BUSINESS INTELLIGENCE</div>
      <h1 style="margin:6px 0 4px; font-size:22px; font-weight:700; letter-spacing:-0.02em;">互盛情報中樞 · 標案監控通報</h1>
      <div style="font-size:12px; color:#cdd8d1;">發送日期：{taipei_date_str} · 本次為您偵測到 <strong>{len(tenders)}</strong> 筆關注縣市新標案</div>
    </div>

    <!-- Content -->
    <div style="padding:24px 28px;">
      <div style="background:#eaf2eb; border-radius:6px; padding:12px 16px; margin-bottom:20px; font-size:12px; color:#2f5146; line-height:1.6;">
        🔔 您好！系統依據您所訂閱之縣市條件，自動為您比對出今日最新公告與公開徵求之影印機/事務機採購標案。本信件已自動排除重複通報。
      </div>

      {items_html}

      <div style="text-align:center; margin-top:28px; padding-top:20px; border-top:1px dashed #d4ded7;">
        <a href="https://gyuyu2002-jeff.github.io/ricoh-intel-hub/" target="_blank" style="display:inline-block; background:#202825; color:#ffffff; font-size:13px; font-weight:700; padding:10px 24px; border-radius:6px; text-decoration:none;">
          前往 互盛情報中樞 線上完整雷達 ➜
        </a>
      </div>
    </div>

    <!-- Footer -->
    <div style="background:#f4f7f4; padding:16px 28px; font-size:11px; color:#849289; text-align:center; border-top:1px solid #e1e9e2;">
      發件信箱：huxen.ricoh@gmail.com · 此為互盛內部業務情報系統自動發送之快報<br>
      若欲修改訂閱縣市或取消訂閱，請至 <a href="https://gyuyu2002-jeff.github.io/ricoh-intel-hub/" style="color:#c92d3f; text-decoration:none;">互盛情報中樞首頁</a> 點選「訂閱標案」進行更新。
    </div>
  </div>
</body>
</html>"""
    return html


def send_email_smtp(to_email, subject, html_content, mail_user, mail_pass):
    """
    Sends an email using Gmail SMTP.
    """
    msg = MIMEMultipart("alternative")
    msg["From"] = f"互盛情報中樞 <{mail_user}>"
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.attach(MIMEText(html_content, "html", "utf-8"))

    server = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=20)
    server.ehlo()
    server.starttls()
    server.ehlo()
    server.login(mail_user, mail_pass)
    server.sendmail(mail_user, [to_email], msg.as_string())
    server.quit()


def dispatch_alerts(dry_run=False, test_email=None):
    mail_user = os.environ.get("MAIL_USERNAME", "huxen.ricoh@gmail.com").strip()
    mail_pass = os.environ.get("MAIL_PASSWORD", "").strip()

    if not dry_run and not mail_pass:
        print("Warning: MAIL_PASSWORD environment variable is not set. Running in dry-run mode.")
        dry_run = True

    data = load_json_file(DATA_FILE)
    tenders = data.get("tenders", [])
    if not tenders:
        print("No tenders found in data.json. Nothing to alert.")
        return 0

    sent_logs = load_json_file(SENT_LOG_FILE, default_val={})

    taipei_now = datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=8)))
    taipei_date_str = taipei_now.strftime("%Y-%m-%d")

    subscribers = get_subscribers()
    if test_email:
        subscribers = [{"email": test_email, "cities": ["全部"]}]

    if not subscribers:
        print("No subscribers configured. Add subscribers to subscribers.json or set SUBSCRIBERS_URL.")
        return 0

    print(f"Loaded {len(subscribers)} subscribers. Checking {len(tenders)} tenders...")
    sent_count = 0
    new_fingerprints = {}

    for sub in subscribers:
        email = sub.get("email", "").strip()
        if not email:
            continue

        matching_tenders = match_tenders_for_subscriber(sub, tenders, sent_logs)
        if not matching_tenders:
            continue

        subject = f"【互盛情報】今日新增 {len(matching_tenders)} 筆關注標案通報 ({taipei_date_str})"
        html_body = build_email_html(email, matching_tenders, taipei_date_str)

        print(f"Sending alert to {email} ({len(matching_tenders)} tenders matching {sub.get('cities', '全部')})...")

        if dry_run:
            print(f"[DRY-RUN] Would send email to {email} with subject: '{subject}'")
            for t in matching_tenders:
                fp = generate_fingerprint(email, t)
                new_fingerprints[fp] = {
                    "email": email,
                    "job_number": t.get("job_number"),
                    "title": t.get("title"),
                    "sent_at": taipei_now.strftime("%Y-%m-%d %H:%M:%S"),
                    "dry_run": True
                }
            sent_count += 1
        else:
            try:
                send_email_smtp(email, subject, html_body, mail_user, mail_pass)
                for t in matching_tenders:
                    fp = generate_fingerprint(email, t)
                    new_fingerprints[fp] = {
                        "email": email,
                        "job_number": t.get("job_number"),
                        "title": t.get("title"),
                        "sent_at": taipei_now.strftime("%Y-%m-%d %H:%M:%S")
                    }
                sent_count += 1
                print(f"Successfully delivered alert to {email}.")
            except Exception as e:
                print(f"Error sending to {email}: {e}")

    if not dry_run and new_fingerprints:
        sent_logs.update(new_fingerprints)
        save_json_file(SENT_LOG_FILE, sent_logs)
        print(f"Recorded {len(new_fingerprints)} new notification fingerprints in {SENT_LOG_FILE}.")

    return sent_count


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Send email alerts for Ricoh Intel Hub tenders.")
    parser.add_argument("--dry-run", action="store_true", help="Simulate without actually sending emails or modifying sent_notifications.json")
    parser.add_argument("--test-email", type=str, help="Send a test alert email to a specific address")
    args = parser.parse_args()

    dispatched = dispatch_alerts(dry_run=args.dry_run, test_email=args.test_email)
    print(f"Alert dispatch completed. Total subscribers notified: {dispatched}")
