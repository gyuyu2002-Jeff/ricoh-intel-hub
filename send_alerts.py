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


ALLOWED_DOMAINS = ["eosasc.com.tw", "gmail.com"]


def is_allowed_domain(email):
    """
    Validates that email belongs strictly to permitted domains (@eosasc.com.tw, @gmail.com).
    Strictly protects against external abuse and quota depletion.
    """
    if not email or "@" not in email:
        return False
    domain = email.strip().lower().split("@")[-1]
    return domain in ALLOWED_DOMAINS


def get_subscribers():
    """
    Fetch subscriber list.
    Prioritizes remote Google Apps Script / Sheet API if SUBSCRIBERS_URL is set,
    otherwise falls back to local subscribers.json.
    Filters out unsubscribed users and non-whitelisted domains.
    """
    raw_subscribers = []
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
                    raw_subscribers = data
                elif isinstance(data, dict) and "subscribers" in data:
                    raw_subscribers = data["subscribers"]
        except Exception as e:
            print(f"Notice: Failed to fetch remote subscribers ({e}). Falling back to local file.")

    if not raw_subscribers:
        local_data = load_json_file(SUBSCRIBERS_FILE, default_val=[])
        if isinstance(local_data, list):
            raw_subscribers = local_data
        elif isinstance(local_data, dict):
            raw_subscribers = local_data.get("subscribers", [])

    valid_subscribers = []
    for sub in raw_subscribers:
        email = sub.get("email", "").strip().lower()
        status = str(sub.get("status", "有效"))
        if not is_allowed_domain(email):
            continue
        if "停用" in status or "退訂" in status:
            continue
        valid_subscribers.append(sub)

    return valid_subscribers


def unsubscribe_email(email):
    """
    Marks an email as unsubscribed in local subscribers.json.
    """
    email_clean = email.strip().lower()
    local_data = load_json_file(SUBSCRIBERS_FILE, default_val=[])
    updated = False
    if isinstance(local_data, list):
        for sub in local_data:
            if sub.get("email", "").strip().lower() == email_clean:
                sub["status"] = "已停用 (使用者取消訂閱)"
                sub["unsubscribed_at"] = datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S")
                updated = True
        if updated:
            save_json_file(SUBSCRIBERS_FILE, local_data)
            print(f"Subscriber {email_clean} has been marked as unsubscribed in {SUBSCRIBERS_FILE}.")
            return True
    print(f"Subscriber {email_clean} not found in local subscribers.json.")
    return False


def deduplicate_subscribers(subscribers):
    """
    Deduplicates subscribers by email so that the latest registration/preference
    for any given email takes effect, preventing duplicates.
    """
    by_email = {}
    for sub in subscribers:
        email = sub.get("email", "").strip().lower()
        if not is_allowed_domain(email):
            continue
        by_email[email] = sub
    return list(by_email.values())


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
    Filters tenders matching subscriber's cities and categories that have not been sent yet.
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

    # Subscribed categories (copier / peripherals): defaults to ['copier'] for backward compatibility
    sub_categories = subscriber.get("categories", ["copier"])
    if isinstance(sub_categories, str):
        sub_categories = [c.strip() for c in sub_categories.split(",") if c.strip()]
    if not sub_categories:
        sub_categories = ["copier"]

    matching = []
    for tender in tenders:
        city = tender.get("city", "")
        if not is_all_cities and city not in subscribed_cities:
            continue

        tender_stream = tender.get("stream") or tender.get("relevance", {}).get("stream", "copier")
        if tender_stream not in sub_categories:
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

        stream = t.get("stream") or t.get("relevance", {}).get("stream", "copier")
        sub_type = t.get("sub_type") or t.get("relevance", {}).get("sub_type", "main")
        is_peripheral = stream == "peripherals"
        stream_badge_bg = "#fef3c7" if is_peripheral else "#edf4ef"
        stream_badge_color = "#92400e" if is_peripheral else "#2f5146"
        stream_label = "🖨️ 周邊耗材" if is_peripheral else "🏢 事務主機"
        if is_peripheral:
            if sub_type == "supplies":
                stream_label = "🖨️ 碳粉耗材"
            elif sub_type == "printer":
                stream_label = "🖨️ 印表設備"
            elif sub_type == "scanner":
                stream_label = "📄 文件掃描"

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
              <span style="display:inline-block; background:{stream_badge_bg}; color:{stream_badge_color}; font-size:11px; font-weight:700; padding:3px 8px; border-radius:4px; margin-right:6px;">{stream_label}</span>
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

    <!-- Footer & Subscription Management -->
    <div style="background:#f4f7f4; padding:22px 28px; text-align:center; border-top:1px solid #e1e9e2; line-height:1.7;">
      <div style="font-size:12px; color:#53645b; margin-bottom:12px;">
        發件來源：<code>huxen.ricoh@gmail.com</code> · 本信件發送至 <strong>{subscriber_email}</strong>
      </div>
      <div style="margin:14px 0 10px;">
        <a href="https://gyuyu2002-jeff.github.io/ricoh-intel-hub/" target="_blank" style="display:inline-block; padding:8px 18px; margin:0 5px 6px; background:#ffffff; border:1px solid #c9d8ce; color:#2f5146; border-radius:6px; text-decoration:none; font-weight:700; font-size:12px;">
          ⚙️ 變更通知縣市
        </a>
        <a href="https://gyuyu2002-jeff.github.io/ricoh-intel-hub/?action=unsubscribe&amp;email={urllib.parse.quote(subscriber_email.strip().lower())}" target="_blank" style="display:inline-block; padding:8px 18px; margin:0 5px 6px; background:#fff1f2; border:1px solid #fecdd3; color:#be123c; border-radius:6px; text-decoration:none; font-weight:700; font-size:12px;">
          🚫 立即取消訂閱此信箱
        </a>
      </div>
      <div style="font-size:11px; color:#849289; margin-top:8px;">
        點擊「立即取消訂閱」後將立刻自通報名單中移除，系統往後將不再發送任何新案通知信。
      </div>
    </div>
  </div>
</body>
</html>"""
    return html


def build_welcome_email_html(subscriber_email, cities=None, sample_tenders=None):
    """
    Builds an onboarding/test confirmation email for newly registered or updated subscribers.
    Matches the Neo-Editorial theme.
    """
    if cities is None:
        cities = ["全部"]
    if isinstance(cities, list):
        is_all = not cities or any(c in ["全部", "全台", "全台所有縣市", "全部縣市", "ALL"] for c in cities)
        cities_str = "全台所有縣市（22 縣市全數監控）" if is_all else "、".join(cities)
    else:
        cities_str = str(cities)

    sample_section = ""
    if sample_tenders:
        sample_rows = ""
        for t in sample_tenders[:2]:
            tender_url = t.get("tender_url", "https://web.pcc.gov.tw/")
            sample_rows += f"""
            <div style="background:#ffffff; border:1px solid #d4ded7; border-left:3px solid #c92d3f; border-radius:6px; padding:12px 14px; margin-bottom:10px;">
              <div style="font-size:11px; color:#53605a; margin-bottom:4px;">
                <span style="background:#edf4ef; color:#2f5146; font-weight:700; padding:2px 6px; border-radius:3px; margin-right:4px;">{t.get('city', '未知')}</span>
                <span>{t.get('unit', '')}</span> · 案號 {t.get('job_number', '')}
              </div>
              <div style="font-weight:700; font-size:13px; color:#202825; margin-bottom:4px;">
                <a href="{tender_url}" target="_blank" style="color:#202825; text-decoration:none;">{t.get('title', '')}</a>
              </div>
              <div style="font-size:11px; color:#78857d;">預算金額：<strong>{t.get('budget', '未公開')}</strong> · 截止日期：<span style="color:#c92d3f; font-weight:700;">{t.get('deadline', '')}</span></div>
            </div>
            """
        sample_section = f"""
        <div style="margin-top:20px; padding-top:16px; border-top:1px dashed #d4ded7;">
          <div style="font-size:12px; font-weight:700; color:#202825; margin-bottom:10px;">📋 目前最新監控標案範例：</div>
          {sample_rows}
        </div>
        """

    html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>互盛情報中樞 - 通知設定成功（收信功能測試）</title>
</head>
<body style="margin:0; padding:24px 12px; background:#eef3ed; font-family:'Noto Sans TC', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; color:#202825;">
  <div style="max-width:640px; margin:0 auto; background:#fbfcf8; border:1px solid #d4ded7; border-radius:12px; overflow:hidden; box-shadow:0 8px 30px rgba(38,61,52,0.06);">
    <!-- Header -->
    <div style="background:#202825; color:#ffffff; padding:24px 28px; border-bottom:3px solid #c92d3f;">
      <div style="font-size:10px; font-weight:700; letter-spacing:0.12em; color:#a3b2a8; text-transform:uppercase;">RICOH INTERNAL BUSINESS INTELLIGENCE</div>
      <h1 style="margin:6px 0 4px; font-size:22px; font-weight:700; letter-spacing:-0.02em;">互盛情報中樞 · 通知設定成功</h1>
      <div style="font-size:12px; color:#cdd8d1;">收信功能驗證測試 · 標案雷達已正式啟動</div>
    </div>

    <!-- Content -->
    <div style="padding:24px 28px;">
      <div style="background:#eaf2eb; border-left:4px solid #2f5146; border-radius:4px; padding:14px 16px; margin-bottom:20px;">
        <div style="font-size:14px; font-weight:700; color:#2f5146; margin-bottom:4px;">🎉 信箱連通測試成功！</div>
        <div style="font-size:12px; color:#3a584c; line-height:1.6;">
          您好！收到此信代表您的信箱已順利與「互盛情報中樞」完成對接，往後每日比對到符合您關注縣市的影印機/事務機新標案或公開徵求時，系統將主動發送通報信給您。
        </div>
      </div>

      <div style="background:#ffffff; border:1px solid #e2ece4; border-radius:8px; padding:18px 20px; margin-bottom:16px;">
        <div style="font-size:13px; font-weight:700; color:#202825; margin-bottom:12px; border-bottom:1px solid #edf2ee; padding-bottom:8px;">
          📌 您的訂閱監控設定
        </div>
        <table style="width:100%; font-size:12px; line-height:1.8; color:#4a5851;">
          <tr>
            <td style="width:90px; font-weight:700; color:#6b7c73;">通知信箱：</td>
            <td><code style="background:#f4f7f4; padding:2px 6px; border-radius:4px; color:#202825; font-size:12px;">{subscriber_email}</code></td>
          </tr>
          <tr>
            <td style="font-weight:700; color:#6b7c73;">關注地區：</td>
            <td><strong>{cities_str}</strong></td>
          </tr>
          <tr>
            <td style="font-weight:700; color:#6b7c73;">監控標的：</td>
            <td>影印機、多功能複合機、耗材採購、租賃案、公開徵求</td>
          </tr>
          <tr>
            <td style="font-weight:700; color:#6b7c73;">通報頻率：</td>
            <td>每日自動排程多次巡檢比對，有新案即彙整通知（具指紋防重複機制）</td>
          </tr>
          <tr>
            <td style="font-weight:700; color:#6b7c73;">發信來源：</td>
            <td><code>huxen.ricoh@gmail.com</code></td>
          </tr>
        </table>
      </div>

      {sample_section}

      <div style="background:#fcfbf6; border:1px solid #f1e9d2; border-radius:6px; padding:12px 16px; margin-top:16px; font-size:11px; color:#7d6b38; line-height:1.6;">
        💡 <strong>防漏信提醒：</strong>若此信件位於「促銷內容」或「垃圾郵件」匣，請務必點選「非垃圾郵件」並將 <code>huxen.ricoh@gmail.com</code> 新增至通訊錄，以確保往後商機第一時間不漏接。
      </div>

      <div style="text-align:center; margin-top:24px; padding-top:16px; border-top:1px dashed #d4ded7;">
        <a href="https://gyuyu2002-jeff.github.io/ricoh-intel-hub/" target="_blank" style="display:inline-block; background:#202825; color:#ffffff; font-size:13px; font-weight:700; padding:10px 24px; border-radius:6px; text-decoration:none;">
          前往 互盛情報中樞 完整看板 ➜
        </a>
      </div>
    </div>

    <!-- Footer & Subscription Management -->
    <div style="background:#f4f7f4; padding:22px 28px; text-align:center; border-top:1px solid #e1e9e2; line-height:1.7;">
      <div style="font-size:12px; color:#53645b; margin-bottom:12px;">
        發件來源：<code>huxen.ricoh@gmail.com</code> · 此為互盛內部業務情報系統自動發送之設定確認信
      </div>
      <div style="margin:14px 0 10px;">
        <a href="https://gyuyu2002-jeff.github.io/ricoh-intel-hub/" target="_blank" style="display:inline-block; padding:8px 18px; margin:0 5px 6px; background:#ffffff; border:1px solid #c9d8ce; color:#2f5146; border-radius:6px; text-decoration:none; font-weight:700; font-size:12px;">
          ⚙️ 變更通知縣市
        </a>
        <a href="https://gyuyu2002-jeff.github.io/ricoh-intel-hub/?action=unsubscribe&amp;email={urllib.parse.quote(subscriber_email.strip().lower())}" target="_blank" style="display:inline-block; padding:8px 18px; margin:0 5px 6px; background:#fff1f2; border:1px solid #fecdd3; color:#be123c; border-radius:6px; text-decoration:none; font-weight:700; font-size:12px;">
          🚫 立即取消訂閱此信箱
        </a>
      </div>
      <div style="font-size:11px; color:#849289; margin-top:8px;">
        若此設定非您本人操作或不想再收到情報信，點擊「立即取消訂閱」即可自通報名單中移除。
      </div>
    </div>
  </div>
</body>
</html>"""
    return html


def send_welcome_email(email, cities=None, mail_user=None, mail_pass=None, sample_tenders=None, dry_run=False):
    """
    Dispatches onboarding/test confirmation email to verify inbox delivery.
    """
    if not mail_user:
        mail_user = os.environ.get("MAIL_USERNAME", "huxen.ricoh@gmail.com").strip()
    if not mail_pass:
        mail_pass = os.environ.get("MAIL_PASSWORD", "").strip()

    subject = "【互盛情報中樞】通知設定成功測試信 · 標案監控已啟動"
    html_body = build_welcome_email_html(email, cities, sample_tenders)

    if dry_run:
        print(f"[DRY-RUN] Would send welcome test email to {email}")
        return True

    if not mail_pass:
        print(f"Warning: MAIL_PASSWORD not set. Cannot send welcome test email to {email}.")
        return False

    try:
        send_email_smtp(email, subject, html_body, mail_user, mail_pass)
        print(f"Successfully delivered welcome test email to {email}.")
        return True
    except Exception as e:
        print(f"Error sending welcome test email to {email}: {e}")
        return False


def create_email_message(to_email, subject, html_content, mail_user):
    """
    Constructs a MIMEMultipart email message with HTML content and RFC 8058 / RFC 2369 List-Unsubscribe headers.
    """
    msg = MIMEMultipart("alternative")
    msg["From"] = f"互盛情報中樞 <{mail_user}>"
    msg["To"] = to_email
    msg["Subject"] = subject

    # RFC 8058 / RFC 2369: Allows Gmail/Outlook/Apple Mail to render a native "Unsubscribe" button at the top
    unsub_url = f"https://gyuyu2002-jeff.github.io/ricoh-intel-hub/?action=unsubscribe&email={urllib.parse.quote(to_email.strip().lower())}"
    msg["List-Unsubscribe"] = f"<{unsub_url}>"
    msg["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"

    msg.attach(MIMEText(html_content, "html", "utf-8"))
    return msg


def send_email_smtp(to_email, subject, html_content, mail_user, mail_pass):
    """
    Sends an email using Gmail SMTP.
    """
    msg = create_email_message(to_email, subject, html_content, mail_user)

    server = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=20)
    server.ehlo()
    server.starttls()
    server.ehlo()
    server.login(mail_user, mail_pass)
    server.sendmail(mail_user, [to_email], msg.as_string())
    server.quit()


def dispatch_alerts(dry_run=False, test_email=None, send_welcome_to=None):
    mail_user = os.environ.get("MAIL_USERNAME", "huxen.ricoh@gmail.com").strip()
    mail_pass = os.environ.get("MAIL_PASSWORD", "").strip()

    if not dry_run and not mail_pass:
        print("Warning: MAIL_PASSWORD environment variable is not set. Running in dry-run mode.")
        dry_run = True

    data = load_json_file(DATA_FILE)
    tenders = data.get("tenders", [])
    sent_logs = load_json_file(SENT_LOG_FILE, default_val={})

    taipei_now = datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=8)))
    taipei_date_str = taipei_now.strftime("%Y-%m-%d")

    # If specifically requesting a welcome test email for a target address
    if send_welcome_to:
        print(f"Sending targeted welcome test email to {send_welcome_to}...")
        success = send_welcome_email(
            send_welcome_to,
            cities=["全部"],
            mail_user=mail_user,
            mail_pass=mail_pass,
            sample_tenders=tenders,
            dry_run=dry_run
        )
        if success and not dry_run:
            norm_email = send_welcome_to.strip().lower()
            sent_logs[f"welcome_{norm_email}"] = {
                "email": send_welcome_to,
                "type": "welcome_test",
                "sent_at": taipei_now.strftime("%Y-%m-%d %H:%M:%S")
            }
            save_json_file(SENT_LOG_FILE, sent_logs)
        return 1 if success else 0

    if not tenders:
        print("No tenders found in data.json. Nothing to alert.")
        return 0

    subscribers = get_subscribers()
    if test_email:
        subscribers = [{"email": test_email, "cities": ["全部"]}]
    else:
        subscribers = deduplicate_subscribers(subscribers)

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

        norm_email = email.lower()
        welcome_key = f"welcome_{norm_email}"

        # 1. 確保每位設定成功的使用者都先收到一封測試確認信，驗證信箱可正常收信
        if welcome_key not in sent_logs and not test_email:
            print(f"New subscriber detected ({email}). Sending welcome/test verification email...")
            if dry_run:
                print(f"[DRY-RUN] Would send welcome test email to {email}")
                new_fingerprints[welcome_key] = {
                    "email": email,
                    "type": "welcome_test",
                    "sent_at": taipei_now.strftime("%Y-%m-%d %H:%M:%S"),
                    "dry_run": True
                }
            else:
                success = send_welcome_email(
                    email,
                    cities=sub.get("cities", ["全部"]),
                    mail_user=mail_user,
                    mail_pass=mail_pass,
                    sample_tenders=tenders
                )
                if success:
                    new_fingerprints[welcome_key] = {
                        "email": email,
                        "type": "welcome_test",
                        "sent_at": taipei_now.strftime("%Y-%m-%d %H:%M:%S")
                    }

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
    parser.add_argument("--send-welcome", type=str, help="Send a welcome test email to a specific address to verify mailbox reception")
    parser.add_argument("--unsubscribe", type=str, help="Unsubscribe an email address from alert notifications")
    args = parser.parse_args()

    if args.unsubscribe:
        ok = unsubscribe_email(args.unsubscribe)
        sys.exit(0 if ok else 1)

    dispatched = dispatch_alerts(dry_run=args.dry_run, test_email=args.test_email, send_welcome_to=args.send_welcome)
    print(f"Alert dispatch completed. Total subscribers notified: {dispatched}")
