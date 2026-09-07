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

if sys.platform == "win32":
    import io
    try:
        if hasattr(sys.stdout, "buffer"):
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        if hasattr(sys.stderr, "buffer"):
            sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
    except Exception:
        pass

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

# Gmail Daily Sending Quota & Circuit Breaker Limits (Consumer Gmail @gmail.com)
GMAIL_DAILY_LIMIT = 500
QUOTA_WARN_THRESHOLD = 400          # 80%: 第一階段警示提醒
QUOTA_CRITICAL_THRESHOLD = 450      # 90%: 第二階段高危告警
QUOTA_CIRCUIT_BREAKER = 485         # 97%: 自動熔斷保護，停止批次推播保留底線
DEFAULT_ADMIN_EMAIL = "gyuyu2002@gmail.com"


def clean_and_count_rolling_deliveries(sent_logs, now=None, window_hours=24, prune_hours=48):
    """
    Cleans up delivery history entries older than prune_hours (default 48h)
    and counts real deliveries dispatched within the rolling window_hours (default 24h).
    Returns (count_24h, oldest_in_window_dt).
    """
    if now is None:
        now = datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=8)))

    cutoff = now - timedelta(hours=window_hours)
    retention_cutoff = now - timedelta(hours=prune_hours)

    history = sent_logs.get("_delivery_history", [])
    valid_24h = []
    retained_history = []

    for item in history:
        ts_str = item.get("sent_at", "")
        if not ts_str:
            continue
        try:
            if "T" in ts_str:
                item_dt = datetime.fromisoformat(ts_str)
                if item_dt.tzinfo is None:
                    item_dt = item_dt.replace(tzinfo=timezone(timedelta(hours=8)))
            else:
                item_dt = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone(timedelta(hours=8)))
        except Exception:
            continue

        if item_dt >= retention_cutoff:
            retained_history.append(item)
        if item_dt >= cutoff and not item.get("dry_run", False):
            valid_24h.append((item_dt, item))

    sent_logs["_delivery_history"] = retained_history
    oldest_in_window = min([dt for dt, _ in valid_24h]) if valid_24h else None
    return len(valid_24h), oldest_in_window


def log_email_delivery(sent_logs, recipient, delivery_type="digest", dry_run=False, now=None):
    """
    Appends an email delivery entry into _delivery_history in sent_logs.
    """
    if now is None:
        now = datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=8)))
    if "_delivery_history" not in sent_logs or not isinstance(sent_logs["_delivery_history"], list):
        sent_logs["_delivery_history"] = []
    entry = {
        "sent_at": now.strftime("%Y-%m-%d %H:%M:%S"),
        "recipient": recipient,
        "type": delivery_type,
        "dry_run": bool(dry_run)
    }
    sent_logs["_delivery_history"].append(entry)


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


def generate_forecast_fingerprint(email, forecast):
    """
    Create an immutable unique key for a forecast notification.
    Key structure: email : forecast_id : predicted_month
    """
    f_id = forecast.get("id", "unknown")
    p_month = forecast.get("predicted_month", "unknown")
    norm_email = email.strip().lower()
    return f"{norm_email}_forecast_{f_id}_{p_month}"


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

    # Subscribed categories (copier / forecast): defaults to ['copier'] for backward compatibility
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


def match_forecasts_for_subscriber(subscriber, forecasts, sent_logs):
    """
    Filters upcoming copier forecasts matching subscriber's cities and categories that have not been sent yet.
    """
    norm_email = subscriber.get("email", "").strip().lower()
    if not norm_email or "@" not in norm_email:
        return []

    subscribed_cities = subscriber.get("cities", [])
    if isinstance(subscribed_cities, str):
        subscribed_cities = [c.strip() for c in subscribed_cities.split(",") if c.strip()]

    is_all_cities = not subscribed_cities or any(
        c in ["全部", "全部縣市", "全台", "全台所有縣市", "ALL"] for c in subscribed_cities
    )

    sub_categories = subscriber.get("categories", ["copier"])
    if isinstance(sub_categories, str):
        sub_categories = [c.strip() for c in sub_categories.split(",") if c.strip()]
    if not sub_categories:
        sub_categories = ["copier"]

    # Support "forecast" or legacy "peripherals" preference
    wants_forecast = ("forecast" in sub_categories) or ("peripherals" in sub_categories)
    if not wants_forecast:
        return []

    matching = []
    for fc in forecasts:
        city = fc.get("city", "")
        if not is_all_cities and city not in subscribed_cities:
            continue

        fingerprint = generate_forecast_fingerprint(norm_email, fc)
        if fingerprint in sent_logs:
            continue

        matching.append(fc)

    return matching


def build_email_html(subscriber_email, tenders, taipei_date_str, forecasts=None):
    """
    Builds a Neo-Editorial HTML email matching the Ricoh Intel Hub theme.
    Supports both active tenders and 6-month copier forecasts.
    """
    if forecasts is None:
        forecasts = []

    # 1. Active tenders section
    items_html = ""
    if tenders:
        items_html += f"""
        <div style="margin-bottom:12px; padding-bottom:6px; border-bottom:2px solid #202825; display:flex; justify-content:space-between; align-items:center;">
          <h2 style="margin:0; font-size:15px; color:#202825; font-weight:700;">🏢 本日最新公告與進行中案件（共 {len(tenders)} 筆）</h2>
          <span style="font-size:11px; color:#78857d;">即時採購公告雷達</span>
        </div>
        """
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
            stream_label = "🖨️ 周邊耗材" if is_peripheral else "🏢 影印機主機"
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

    # 2. Upcoming forecasts section
    forecasts_html = ""
    if forecasts:
        forecasts_html += f"""
        <div style="margin:28px 0 12px; padding-bottom:6px; border-bottom:2px solid #2f5146; display:flex; justify-content:space-between; align-items:center;">
          <h2 style="margin:0; font-size:15px; color:#2f5146; font-weight:700;">🔮 推測未來上架案件 · 未來 6 個月換約預警（共 {len(forecasts)} 筆）</h2>
          <span style="font-size:11px; color:#78857d;">同機關同案名歷史規律推估</span>
        </div>
        """
        for fc in forecasts:
            incumbent_info = fc.get("incumbent", {})
            incumbent_type = incumbent_info.get("type", "other")
            is_husheng = incumbent_type in ["husheng", "ricoh"]
            is_comp = incumbent_type == "competitor"
            inc_badge_bg = "#f0fdf4" if is_husheng else "#fff1f2" if is_comp else "#f1f5f9"
            inc_badge_color = "#15803d" if is_husheng else "#be123c" if is_comp else "#475569"
            inc_badge_label = incumbent_info.get("label", "⚪ 廠商防守中")

            days = fc.get("days_until", 999)
            countdown_bg = "#fee2e2" if days <= 30 else "#fef3c7" if days <= 60 else "#edf4ef"
            countdown_color = "#991b1b" if days <= 30 else "#92400e" if days <= 60 else "#2f5146"
            countdown_label = fc.get("countdown_label", "推估換約")

            expansion_info = fc.get("expansion", {})
            has_ext = expansion_info.get("has_extension", False)

            cur_status = fc.get("current_status", {})
            is_solicitation = cur_status.get("status") == "solicitation"

            pcc_search_url = f"https://web.pcc.gov.tw/prkms/prms-viewTenderDetailClient.do?ds={fc.get('unit_id','')}"

            # History track summary with direct links
            history_track_html = ""
            if fc.get("history_track"):
                track_pills = []
                for h in fc.get("history_track", []):
                    pill_text = f"#{h.get('index')} {h.get('month')} · {h.get('winner')} (折率{h.get('discount_rate','-')}%)"
                    if h.get("source_url"):
                        track_pills.append(
                            f"""<a href="{h.get('source_url')}" target="_blank" style="display:inline-block; background:#f4f7f4; border:1px solid #dce6de; color:#2f5146; text-decoration:none; padding:2px 6px; border-radius:4px; font-size:10px; margin:2px 4px 2px 0;">
                                {pill_text} ↗
                            </a>"""
                        )
                    else:
                        track_pills.append(
                            f"""<span style="display:inline-block; background:#f4f7f4; border:1px solid #dce6de; padding:2px 6px; border-radius:4px; font-size:10px; margin:2px 4px 2px 0;">
                                {pill_text}
                            </span>"""
                        )
                if is_solicitation:
                    track_pills.append(
                        f"""<span style="display:inline-block; background:#fff7ed; border:1px solid #fed7aa; color:#c2410c; font-weight:700; padding:2px 6px; border-radius:4px; font-size:10px; margin:2px 4px 2px 0;">
                            🔥 本期已公開徵求：{cur_status.get('date')}（案號 {cur_status.get('job_number')}）
                        </span>"""
                    )
                else:
                    track_pills.append(
                        f"""<span style="display:inline-block; background:#fef2f2; border:1px solid #fecaca; color:#b91c1c; font-weight:700; padding:2px 6px; border-radius:4px; font-size:10px; margin:2px 4px 2px 0;">
                            🔮 預估 #{len(fc.get('history_track',[]))+1} {fc.get('predicted_month')}
                        </span>"""
                    )
                history_track_html = f"""
                <div style="margin-top:8px; padding-top:8px; border-top:1px dashed #e2ece4; font-size:11px; color:#53605a;">
                  <strong>歷史開標履歷（可點擊查看各次決標）：</strong><div style="margin-top:4px;">{''.join(track_pills)}</div>
                </div>
                """

            ext_alert_html = ""
            if has_ext:
                ext_alert_html = f"""
                <div style="background:#fffbeb; border:1px solid #fde68a; border-left:3px solid #d97706; padding:8px 12px; border-radius:5px; margin-top:8px; font-size:11px; color:#92400e; line-height:1.5;">
                  <strong>⚡ 擴充條款提醒：</strong>{expansion_info.get('notice', '')}
                </div>
                """

            solicitation_banner_html = ""
            if is_solicitation:
                solicitation_banner_html = f"""
                <div style="background:#fff7ed; border:1px solid #fed7aa; border-left:3px solid #ea580c; padding:8px 12px; border-radius:5px; margin-top:8px; font-size:11px; color:#c2410c; line-height:1.5;">
                  <strong>🔥 【本案已啟動招標前置：公開徵求中】</strong> 機關於 {cur_status.get('date')} 發布「{cur_status.get('title')}」（案號 {cur_status.get('job_number')}），正處於訪價與規格徵詢黃金期，請速提供理光型錄！
                </div>
                """

            status_badge_html = f"""<span style="display:inline-block; background:#fff7ed; color:#ea580c; font-size:11px; font-weight:700; padding:3px 8px; border-radius:4px; margin-right:6px;">🔥 公開徵求中</span>""" if is_solicitation else f"""<span style="display:inline-block; background:{countdown_bg}; color:{countdown_color}; font-size:11px; font-weight:700; padding:3px 8px; border-radius:4px; margin-right:6px;">⏳ {countdown_label}</span>"""

            progress_label = "當前最新進度" if is_solicitation else "預計開標期"
            cur_date = cur_status.get("date", "")
            progress_value = f"🔥 公開徵求中 ({cur_date})" if is_solicitation else fc.get("predicted_range", "推估中")

            action_buttons_html = ""
            if cur_status.get("notice_url"):
                action_buttons_html += f"""<a href="{cur_status.get('notice_url')}" target="_blank" style="display:inline-block; background:#ea580c; color:#ffffff; font-size:11px; font-weight:700; padding:6px 12px; border-radius:4px; text-decoration:none; margin-right:6px;">查看本期公告 ({cur_status.get('stage', '最新')}) ↗</a>"""
            if fc.get("latest_source_url"):
                action_buttons_html += f"""<a href="{fc.get('latest_source_url')}" target="_blank" style="display:inline-block; background:#2f5146; color:#ffffff; font-size:11px; font-weight:700; padding:6px 12px; border-radius:4px; text-decoration:none; margin-right:6px;">查看前次官方決標公告 ↗</a>"""
            action_buttons_html += f"""<a href="{pcc_search_url}" target="_blank" style="display:inline-block; background:#f1f5f9; color:#475569; font-size:11px; font-weight:600; padding:6px 10px; border-radius:4px; text-decoration:none;">機關標案列表 ↗</a>"""

            forecasts_html += f"""
            <div style="background:#ffffff; border:1px solid #d4ded7; border-left:4px solid #2f5146; border-radius:8px; padding:18px 20px; margin-bottom:16px; box-shadow:0 2px 8px rgba(0,0,0,0.03);">
              <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px; flex-wrap:wrap; gap:6px;">
                <div>
                  <span style="display:inline-block; background:#edf4ef; color:#2f5146; font-size:11px; font-weight:700; padding:3px 8px; border-radius:4px; margin-right:6px;">{fc.get('city', '全台')}</span>
                  {status_badge_html}
                  <span style="display:inline-block; background:{inc_badge_bg}; color:{inc_badge_color}; font-size:11px; font-weight:700; padding:3px 8px; border-radius:4px;">{inc_badge_label}</span>
                </div>
                <span style="display:inline-block; background:#f1f5f9; color:#475569; font-size:10px; padding:2px 6px; border-radius:4px;">{expansion_info.get('badge_label', '常態期滿')}</span>
              </div>

              <h3 style="margin:6px 0 6px; font-size:16px; color:#202825; line-height:1.4;">
                <span style="color:#2f5146; font-weight:700;">{'【已啟動徵求】' if is_solicitation else '【推估】'}{cur_status.get('title') if is_solicitation and cur_status.get('title') else fc.get('predicted_title', '')}</span>
              </h3>
              <div style="font-size:12px; color:#53605a; margin-bottom:10px;">
                <strong>發包機關：</strong>{fc.get('unit', '')} · <strong>前次案名：</strong>{fc.get('latest_title', '')}
              </div>

              <table style="width:100%; border-collapse:collapse; background:#fbfcf8; border:1px solid #e2ece4; border-radius:6px; margin-bottom:8px; font-size:12px;">
                <tr>
                  <td style="padding:8px 12px; border-right:1px solid #e2ece4; width:33%;">
                    <div style="color:#8a968f; font-size:10px;">{progress_label}</div>
                    <div style="color:#2f5146; font-weight:700; font-size:14px; margin-top:2px;">{progress_value}</div>
                  </td>
                  <td style="padding:8px 12px; border-right:1px solid #e2ece4; width:33%;">
                    <div style="color:#8a968f; font-size:10px;">前次決標總額</div>
                    <div style="color:#202825; font-weight:700; font-size:14px; margin-top:2px;">{fc.get('latest_award_price_str', '待查')}</div>
                  </td>
                  <td style="padding:8px 12px; width:34%;">
                    <div style="color:#8a968f; font-size:10px;">換約週期規律</div>
                    <div style="color:#202825; font-weight:700; font-size:13px; margin-top:2px;">{fc.get('cadence_summary', '定期換約')}</div>
                  </td>
                </tr>
              </table>

              {solicitation_banner_html}
              {ext_alert_html}
              {history_track_html}

              <div style="margin-top:10px; padding:8px 10px; background:#f4f8f5; border-radius:5px; font-size:11px; color:#2f5146; line-height:1.5;">
                🎯 <strong>業務作戰指引：</strong>{fc.get('action_suggestion', '')}
              </div>

              <div style="margin-top:12px; display:flex; flex-wrap:wrap; gap:6px;">
                {action_buttons_html}
              </div>
            </div>
            """
    summary_parts = []
    if tenders:
        summary_parts.append(f"<strong>{len(tenders)}</strong> 筆關注新標案")
    if forecasts:
        summary_parts.append(f"<strong>{len(forecasts)}</strong> 筆未來換約預警")
    summary_text = " · 本次為您偵測到 " + " 與 ".join(summary_parts) if summary_parts else ""

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
      <div style="font-size:12px; color:#cdd8d1;">發送日期：{taipei_date_str}{summary_text}</div>
    </div>

    <!-- Content -->
    <div style="padding:24px 28px;">
      <div style="background:#eaf2eb; border-radius:6px; padding:12px 16px; margin-bottom:20px; font-size:12px; color:#2f5146; line-height:1.6;">
        🔔 您好！系統依據您所訂閱之縣市與情報類別，自動為您比對出今日最新公告標案與未來 6 個月即將換約之影印機標案推估預警。本信件已自動排除重複通報。
      </div>

      {items_html}
      {forecasts_html}

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
          ⚙️ 變更通知設定
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


def build_welcome_email_html(subscriber_email, cities=None, sample_tenders=None, categories=None, sample_forecasts=None):
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

    if categories is None:
        categories = ["copier", "forecast"]
    if isinstance(categories, str):
        categories = [c.strip() for c in categories.split(",") if c.strip()]

    category_labels = []
    if "copier" in categories:
        category_labels.append("🏢 影印機案件監控")
    if "forecast" in categories or "peripherals" in categories:
        category_labels.append("🔮 推測未來上架案件 (六個月)")
    if not category_labels:
        category_labels.append("🏢 影印機案件監控")
    categories_str = "、".join(category_labels)

    sample_section = ""
    if sample_tenders or sample_forecasts:
        sample_rows = ""
        if sample_tenders:
            for t in sample_tenders[:2]:
                tender_url = t.get("tender_url", "https://web.pcc.gov.tw/")
                sample_rows += f"""
                <div style="background:#ffffff; border:1px solid #d4ded7; border-left:3px solid #c92d3f; border-radius:6px; padding:12px 14px; margin-bottom:10px;">
                  <div style="font-size:11px; color:#53605a; margin-bottom:4px;">
                    <span style="background:#edf4ef; color:#2f5146; font-weight:700; padding:2px 6px; border-radius:3px; margin-right:4px;">{t.get('city', '未知')}</span>
                    <span style="background:#e8f4fd; color:#0c5460; font-weight:700; padding:2px 6px; border-radius:3px; margin-right:4px;">即時標案</span>
                    <span>{t.get('unit', '')}</span> · 案號 {t.get('job_number', '')}
                  </div>
                  <div style="font-weight:700; font-size:13px; color:#202825; margin-bottom:4px;">
                    <a href="{tender_url}" target="_blank" style="color:#202825; text-decoration:none;">{t.get('title', '')}</a>
                  </div>
                  <div style="font-size:11px; color:#78857d;">預算金額：<strong>{t.get('budget', '未公開')}</strong> · 截止日期：<span style="color:#c92d3f; font-weight:700;">{t.get('deadline', '')}</span></div>
                </div>
                """
        if sample_forecasts:
            for fc in sample_forecasts[:2]:
                sample_rows += f"""
                <div style="background:#ffffff; border:1px solid #d4ded7; border-left:3px solid #2f5146; border-radius:6px; padding:12px 14px; margin-bottom:10px;">
                  <div style="font-size:11px; color:#53605a; margin-bottom:4px;">
                    <span style="background:#edf4ef; color:#2f5146; font-weight:700; padding:2px 6px; border-radius:3px; margin-right:4px;">{fc.get('city', '未知')}</span>
                    <span style="background:#f0fdf4; color:#15803d; font-weight:700; padding:2px 6px; border-radius:3px; margin-right:4px;">🔮 推估換約</span>
                    <span>{fc.get('unit', '')}</span>
                  </div>
                  <div style="font-weight:700; font-size:13px; color:#202825; margin-bottom:4px;">
                    【推估】{fc.get('predicted_title', '')}
                  </div>
                  <div style="font-size:11px; color:#78857d;">
                    預計開標期：<strong>{fc.get('predicted_range', '推估中')}</strong> · 前次得標商：<strong>{fc.get('latest_winner', '待查')}</strong>（{fc.get('cadence_summary', '')}）
                  </div>
                </div>
                """
        sample_section = f"""
        <div style="margin-top:20px; padding-top:16px; border-top:1px dashed #d4ded7;">
          <div style="font-size:12px; font-weight:700; color:#202825; margin-bottom:10px;">📋 最新情報通報範例：</div>
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
          您好！收到此信代表您的信箱已順利與「互盛情報中樞」完成對接，往後每日比對到符合您關注縣市的影印機即時標案與未來 6 個月期滿換約推估時，系統將主動發送通報信給您。
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
            <td style="font-weight:700; color:#6b7c73;">關注項目：</td>
            <td><strong>{categories_str}</strong></td>
          </tr>
          <tr>
            <td style="font-weight:700; color:#6b7c73;">監控標的：</td>
            <td>影印機／複合機主機租賃採購、公開徵求、未來 6 個月期滿換約推估與擴充雙重提醒</td>
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
          ⚙️ 變更通知設定
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


def send_welcome_email(email, cities=None, mail_user=None, mail_pass=None, sample_tenders=None, categories=None, sample_forecasts=None, dry_run=False):
    """
    Dispatches onboarding/test confirmation email to verify inbox delivery.
    """
    if not mail_user:
        mail_user = os.environ.get("MAIL_USERNAME", "huxen.ricoh@gmail.com").strip()
    if not mail_pass:
        mail_pass = os.environ.get("MAIL_PASSWORD", "").strip()

    subject = "【互盛情報中樞】通知設定成功測試信 · 標案監控已啟動"
    html_body = build_welcome_email_html(email, cities=cities, sample_tenders=sample_tenders, categories=categories, sample_forecasts=sample_forecasts)

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


def create_email_message(to_email, subject, html_content, mail_user, extra_headers=None):
    """
    Constructs a MIMEMultipart email message with HTML content and RFC 8058 / RFC 2369 List-Unsubscribe headers.
    """
    msg = MIMEMultipart("alternative")
    msg["From"] = f"互盛情報中樞 <{mail_user}>"
    msg["To"] = to_email
    msg["Subject"] = subject

    if extra_headers:
        for k, v in extra_headers.items():
            msg[k] = v

    # RFC 8058 / RFC 2369: Allows Gmail/Outlook/Apple Mail to render a native "Unsubscribe" button at the top
    unsub_url = f"https://gyuyu2002-jeff.github.io/ricoh-intel-hub/?action=unsubscribe&email={urllib.parse.quote(to_email.strip().lower())}"
    msg["List-Unsubscribe"] = f"<{unsub_url}>"
    msg["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"

    msg.attach(MIMEText(html_content, "html", "utf-8"))
    return msg


def send_email_smtp(to_email, subject, html_content, mail_user, mail_pass, extra_headers=None):
    """
    Sends an email using Gmail SMTP.
    """
    msg = create_email_message(to_email, subject, html_content, mail_user, extra_headers=extra_headers)

    server = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=20)
    server.ehlo()
    server.starttls()
    server.ehlo()
    server.login(mail_user, mail_pass)
    server.sendmail(mail_user, [to_email], msg.as_string())
    server.quit()


def build_quota_alert_email_html(admin_email, sent_count, limit, level, oldest_ts=None, subscriber_count=0):
    """
    Generates a high-priority alert email notifying the administrator when Gmail sending quota approaches 500.
    Supports 'warning' (80%), 'critical' (90%), and 'circuit_breaker' (97%) severity levels.
    """
    pct = round((sent_count / limit) * 100, 1)
    remaining = max(0, limit - sent_count)
    is_circuit = (level == "circuit_breaker")
    is_critical = (level == "critical" or is_circuit)

    if is_circuit:
        theme_color = "#b91c1c"
        theme_bg = "#fef2f2"
        badge_text = "🚨 【緊急熔斷】配額已達 97% · 自動暫停推播保護"
        title_text = "Gmail 每日發信配額已達 97% 熔斷保護啟動"
        summary_desc = (
            f"系統監控到目前的 Gmail 發信伺服器在<strong>過去 24 小時內已累計發出 {sent_count} 封郵件</strong>，"
            f"已佔用每日上限（{limit} 封）的 <strong>{pct}%</strong>，目前<strong>僅剩 {remaining} 封</strong>安全可用額度！<br>"
            f"為了避免觸發 Google 官方 24 小時強制鎖信懲罰（<code>550 5.4.5 Daily user-sending quota exceeded</code>），"
            f"系統已<strong>主動暫停後續例行性推播</strong>，保留最後額度以確保管理通訊與系統狀態正常。"
        )
    elif is_critical:
        theme_color = "#dc2626"
        theme_bg = "#fef2f2"
        badge_text = "🚨 【緊急】發信配額高危告警 (90%+)"
        title_text = "Gmail 每日發信額度接近上限通知"
        summary_desc = (
            f"系統監控到目前的 Gmail 發信伺服器在<strong>過去 24 小時內已累計發出 {sent_count} 封郵件</strong>，"
            f"已佔用每日上限（{limit} 封）的 <strong>{pct}%</strong>，目前<strong>僅剩 {remaining} 封</strong>安全可用額度！<br>"
            f"請管理員留意發信量，若發送達到 {QUOTA_CIRCUIT_BREAKER} 封，系統將自動啟動安全熔斷保護。"
        )
    else:
        theme_color = "#d97706"
        theme_bg = "#fffbeb"
        badge_text = "⚠️ 【注意】發信配額用量警戒 (80%+)"
        title_text = "Gmail 每日發信額度用量警戒提醒"
        summary_desc = (
            f"系統監控到目前的 Gmail 發信伺服器在<strong>過去 24 小時內已累計發出 {sent_count} 封郵件</strong>，"
            f"佔用每日上限（{limit} 封）的 <strong>{pct}%</strong>，目前剩餘 <strong>{remaining} 封</strong>額度。<br>"
            f"目前系統運作正常，但發信量已進入 80% 警戒水位，特此先行通知您掌握狀況。"
        )

    reset_hint = ""
    if oldest_ts:
        reset_time = oldest_ts + timedelta(hours=24)
        reset_hint = f"最舊一筆發送紀錄預計於 <strong>{reset_time.strftime('%H:%M')}</strong> 滿 24 小時釋出配額"
    else:
        reset_hint = "發信額度將隨時間滾動釋出"

    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="margin:0; padding:20px; font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif; background:#f4f6f5; color:#1e2923;">
  <div style="max-width:620px; margin:0 auto; background:#ffffff; border-radius:12px; border:1px solid #dbe4de; overflow:hidden; box-shadow:0 4px 16px rgba(0,0,0,0.06);">
    <div style="background:{theme_color}; padding:20px 24px; color:#ffffff;">
      <span style="display:inline-block; background:rgba(255,255,255,0.22); font-size:12px; font-weight:700; padding:3px 10px; border-radius:12px; margin-bottom:8px;">{badge_text}</span>
      <h1 style="margin:0; font-size:20px; font-weight:800; letter-spacing:0.02em;">{title_text}</h1>
      <p style="margin:6px 0 0; font-size:13px; opacity:0.92;">互盛情報中樞 · 郵件推播系統健康監控告警</p>
    </div>
    <div style="padding:24px;">
      <p style="font-size:15px; line-height:1.6; margin-top:0;">
        親愛的情報中樞管理員（<strong>{admin_email}</strong>）您好：
      </p>
      <p style="font-size:14px; line-height:1.7; color:#334155;">
        {summary_desc}
      </p>
      <div style="background:#f8faf9; border:1px solid #e2ece5; border-radius:8px; padding:16px; margin:20px 0;">
        <div style="display:flex; justify-content:space-between; font-size:13px; font-weight:700; margin-bottom:8px;">
          <span>Gmail 24 小時額度消耗：{sent_count} / {limit} 封</span>
          <span style="color:{theme_color};">{pct}%</span>
        </div>
        <div style="width:100%; height:12px; background:#e2e8f0; border-radius:6px; overflow:hidden;">
          <div style="width:{min(100, pct)}%; height:100%; background:{theme_color};"></div>
        </div>
        <div style="display:flex; justify-content:space-between; font-size:11px; color:#64748b; margin-top:8px;">
          <span>目前有效訂閱同仁：{subscriber_count} 位</span>
          <span>{reset_hint}</span>
        </div>
      </div>
      <div style="background:{theme_bg}; border:1px solid {theme_color}33; border-left:4px solid {theme_color}; border-radius:6px; padding:16px; margin-bottom:20px;">
        <strong style="color:{theme_color}; font-size:14px;">💡 系統防護與建議因應對策：</strong>
        <ol style="margin:8px 0 0 18px; padding:0; font-size:13px; color:#334155; line-height:1.75;">
          <li><strong>自動熔斷保護</strong>：系統設有 485 封（97%）硬性熔斷機制，當接近極限時會自動停止大宗推播，絕不讓 Gmail 帳號被 Google 官方停權封鎖 24 小時。</li>
          <li><strong>排程滾動釋放</strong>：Gmail 免費帳號以「滾動 24 小時」計算額度，稍早發送的信件滿 24 小時後將自動釋出新額度。</li>
          <li><strong>升級 Google Workspace</strong>：若訂閱同仁或推播量持續增長，建議將發信信箱升級為企業版 Workspace，每日發信上限將由 500 封大幅提升至 <strong>2,000 封／天</strong>。</li>
          <li><strong>串接專業發信服務</strong>：未來如需支援跨全省數千名同仁或客戶推播，可無縫串接 SendGrid 或 Amazon SES，徹底解除發信限額。</li>
        </ol>
      </div>
      <div style="text-align:center; padding-top:12px; border-top:1px dashed #d4ded7;">
        <a href="https://gyuyu2002-jeff.github.io/ricoh-intel-hub/" target="_blank" style="display:inline-block; background:#202825; color:#ffffff; font-size:13px; font-weight:700; padding:10px 24px; border-radius:6px; text-decoration:none;">
          前往 互盛情報中樞 看板 ➜
        </a>
      </div>
    </div>
    <div style="background:#f4f7f4; padding:16px 24px; text-align:center; font-size:11px; color:#64748b; border-top:1px solid #e1e9e2;">
      發信來源：<code>huxen.ricoh@gmail.com</code> · 監控接收信箱：<code>{admin_email}</code> · 此為系統自動健康通報
    </div>
  </div>
</body>
</html>"""


def check_and_alert_quota(sent_logs, mail_user=None, mail_pass=None, dry_run=False, admin_email=None, subscriber_count=0, now=None, force=False):
    """
    Evaluates rolling 24h email delivery count against Gmail daily quota (500).
    If thresholds (400=80%, 450=90%, 485=circuit_breaker) are reached,
    dispatches high-priority alert email to admin (default: gyuyu2002@gmail.com).
    Suppresses redundant notifications within a 12-hour cooldown unless severity escalates.
    Returns (alerted: bool, level: str, sent_count: int).
    """
    if now is None:
        now = datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=8)))
    if not mail_user:
        mail_user = os.environ.get("MAIL_USERNAME", "huxen.ricoh@gmail.com").strip()
    if not mail_pass:
        mail_pass = os.environ.get("MAIL_PASSWORD", "").strip()

    target_admin = admin_email or os.environ.get("ADMIN_NOTIFY_EMAIL", DEFAULT_ADMIN_EMAIL).strip()

    sent_count, oldest_ts = clean_and_count_rolling_deliveries(sent_logs, now=now)

    if sent_count >= QUOTA_CIRCUIT_BREAKER:
        level = "circuit_breaker"
    elif sent_count >= QUOTA_CRITICAL_THRESHOLD:
        level = "critical"
    elif sent_count >= QUOTA_WARN_THRESHOLD:
        level = "warning"
    else:
        level = "normal"

    if level == "normal" and not force:
        return False, level, sent_count

    if force and level == "normal":
        level = "warning"

    # Cooldown & Escalation Check
    level_rank = {"warning": 1, "critical": 2, "circuit_breaker": 3}
    last_alert = sent_logs.get("_last_quota_alert", {})
    last_level = last_alert.get("level", "")
    last_ts_str = last_alert.get("sent_at", "")

    if not force and last_ts_str:
        try:
            last_dt = datetime.strptime(last_ts_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone(timedelta(hours=8)))
            # 12-hour cooldown for same or lower level
            if (now - last_dt) < timedelta(hours=12):
                if level_rank.get(level, 0) <= level_rank.get(last_level, 0):
                    print(f"Quota alert ({level}, {sent_count}/{GMAIL_DAILY_LIMIT}) throttled: already alerted at {last_ts_str} ({last_level}).")
                    return False, level, sent_count
        except Exception:
            pass

    if level == "circuit_breaker":
        subject = f"🚨【緊急熔斷】Gmail 發信配額已達 {sent_count}/{GMAIL_DAILY_LIMIT} 封！系統已自動暫停推播保護信箱"
    elif level == "critical":
        subject = f"🚨【高危告警】Gmail 發信配額已達 {sent_count}/{GMAIL_DAILY_LIMIT} 封 (90%)！請留意剩餘額度"
    else:
        subject = f"⚠️【用量警戒】Gmail 過去 24 小時已發出 {sent_count}/{GMAIL_DAILY_LIMIT} 封郵件 (80%)"

    html_body = build_quota_alert_email_html(
        target_admin,
        sent_count,
        GMAIL_DAILY_LIMIT,
        level,
        oldest_ts=oldest_ts,
        subscriber_count=subscriber_count
    )

    now_str = now.strftime("%Y-%m-%d %H:%M:%S")

    if dry_run:
        print(f"[DRY-RUN] Would dispatch {level} quota alert to admin ({target_admin}): '{subject}'")
        sent_logs["_last_quota_alert"] = {
            "sent_at": now_str,
            "level": level,
            "sent_count": sent_count,
            "dry_run": True
        }
        return True, level, sent_count

    if not mail_pass:
        print(f"Warning: MAIL_PASSWORD not set. Cannot dispatch quota alert email to {target_admin}.")
        return False, level, sent_count

    try:
        send_email_smtp(
            target_admin,
            subject,
            html_body,
            mail_user,
            mail_pass,
            extra_headers={"X-Priority": "1", "Importance": "High"}
        )
        log_email_delivery(sent_logs, target_admin, delivery_type=f"quota_alert_{level}", dry_run=False, now=now)
        sent_logs["_last_quota_alert"] = {
            "sent_at": now_str,
            "level": level,
            "sent_count": sent_count,
            "dry_run": False
        }
        print(f"Delivered {level} quota alert email to admin {target_admin} (sent: {sent_count}/{GMAIL_DAILY_LIMIT}).")
        return True, level, sent_count
    except Exception as e:
        print(f"Failed to send quota alert to admin {target_admin}: {e}")
        return False, level, sent_count


def update_data_json_quota(data, sent_24h, now_dt):
    """
    Records email quota health status into data.json and client/public/data.json.
    """
    quota_status = {
        "limit": GMAIL_DAILY_LIMIT,
        "used_24h": sent_24h,
        "remaining": max(0, GMAIL_DAILY_LIMIT - sent_24h),
        "usage_percent": round((sent_24h / GMAIL_DAILY_LIMIT) * 100, 1),
        "circuit_breaker_active": sent_24h >= QUOTA_CIRCUIT_BREAKER,
        "status_level": (
            "circuit_breaker" if sent_24h >= QUOTA_CIRCUIT_BREAKER
            else ("critical" if sent_24h >= QUOTA_CRITICAL_THRESHOLD
            else ("warning" if sent_24h >= QUOTA_WARN_THRESHOLD else "normal"))
        ),
        "updated_at": now_dt.strftime("%Y-%m-%d %H:%M:%S")
    }
    data["email_quota_status"] = quota_status
    save_json_file(DATA_FILE, data)
    client_data_file = os.path.join(SCRIPT_DIR, "client", "public", "data.json")
    if os.path.exists(client_data_file):
        try:
            client_data = load_json_file(client_data_file, default_val={})
            client_data["email_quota_status"] = quota_status
            save_json_file(client_data_file, client_data)
        except Exception as e:
            print(f"Notice: Failed to update client/public/data.json quota status: {e}")
    return quota_status


def dispatch_alerts(dry_run=False, test_email=None, send_welcome_to=None, check_quota_only=False, test_quota_alert=False):
    mail_user = os.environ.get("MAIL_USERNAME", "huxen.ricoh@gmail.com").strip()
    mail_pass = os.environ.get("MAIL_PASSWORD", "").strip()

    if not dry_run and not mail_pass:
        print("Warning: MAIL_PASSWORD environment variable is not set. Running in dry-run mode.")
        dry_run = True

    data = load_json_file(DATA_FILE)
    tenders = data.get("tenders", [])
    forecasts = data.get("forecasted_tenders", [])
    sent_logs = load_json_file(SENT_LOG_FILE, default_val={})

    taipei_now = datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=8)))
    taipei_date_str = taipei_now.strftime("%Y-%m-%d")

    # If testing quota alert specifically
    if test_quota_alert:
        admin_target = os.environ.get("ADMIN_NOTIFY_EMAIL", DEFAULT_ADMIN_EMAIL).strip()
        print(f"Triggering test quota alert to admin ({admin_target})...")
        alerted, level, count = check_and_alert_quota(
            sent_logs,
            mail_user=mail_user,
            mail_pass=mail_pass,
            dry_run=dry_run,
            admin_email=admin_target,
            subscriber_count=len(get_subscribers()),
            now=taipei_now,
            force=True
        )
        if not dry_run:
            save_json_file(SENT_LOG_FILE, sent_logs)
        print(f"Test quota alert completed (alerted={alerted}, level={level}, 24h_count={count}).")
        return 1 if alerted else 0

    # If checking quota health only
    if check_quota_only:
        count, oldest = clean_and_count_rolling_deliveries(sent_logs, now=taipei_now)
        pct = round((count / GMAIL_DAILY_LIMIT) * 100, 1)
        print("=== Gmail Daily Quota Health Check ===")
        print(f"Rolling 24h Dispatched: {count} / {GMAIL_DAILY_LIMIT} ({pct}%)")
        print(f"Remaining Headroom: {max(0, GMAIL_DAILY_LIMIT - count)} emails")
        if oldest:
            print(f"Oldest in 24h Window: {oldest.strftime('%Y-%m-%d %H:%M:%S')}")
        alerted, level, _ = check_and_alert_quota(
            sent_logs,
            mail_user=mail_user,
            mail_pass=mail_pass,
            dry_run=dry_run,
            subscriber_count=len(get_subscribers()),
            now=taipei_now
        )
        update_data_json_quota(data, count, taipei_now)
        if not dry_run:
            save_json_file(SENT_LOG_FILE, sent_logs)
        print(f"Status Level: {level.upper()} (Alert triggered: {alerted})")
        return 0

    # If specifically requesting a welcome test email for a target address
    if send_welcome_to:
        print(f"Sending targeted welcome test email to {send_welcome_to}...")
        success = send_welcome_email(
            send_welcome_to,
            cities=["全部"],
            mail_user=mail_user,
            mail_pass=mail_pass,
            sample_tenders=tenders,
            categories=["copier", "forecast"],
            sample_forecasts=forecasts,
            dry_run=dry_run
        )
        if success:
            norm_email = send_welcome_to.strip().lower()
            sent_logs[f"welcome_{norm_email}"] = {
                "email": send_welcome_to,
                "type": "welcome_test",
                "sent_at": taipei_now.strftime("%Y-%m-%d %H:%M:%S"),
                "dry_run": dry_run
            }
            log_email_delivery(sent_logs, send_welcome_to, delivery_type="welcome_test", dry_run=dry_run, now=taipei_now)
            count, _ = clean_and_count_rolling_deliveries(sent_logs, now=taipei_now)
            update_data_json_quota(data, count, taipei_now)
            if not dry_run:
                save_json_file(SENT_LOG_FILE, sent_logs)
        return 1 if success else 0

    if not tenders and not forecasts:
        print("No tenders or forecasts found in data.json. Nothing to alert.")
        count, _ = clean_and_count_rolling_deliveries(sent_logs, now=taipei_now)
        update_data_json_quota(data, count, taipei_now)
        if not dry_run:
            save_json_file(SENT_LOG_FILE, sent_logs)
        return 0

    subscribers = get_subscribers()
    if test_email:
        subscribers = [{"email": test_email, "cities": ["全部"], "categories": ["copier", "forecast"]}]
    else:
        subscribers = deduplicate_subscribers(subscribers)

    if not subscribers:
        print("No subscribers configured. Add subscribers to subscribers.json or set SUBSCRIBERS_URL.")
        count, _ = clean_and_count_rolling_deliveries(sent_logs, now=taipei_now)
        update_data_json_quota(data, count, taipei_now)
        if not dry_run:
            save_json_file(SENT_LOG_FILE, sent_logs)
        return 0

    # Initial Quota & Circuit Breaker Check before batch dispatches
    initial_24h, _ = clean_and_count_rolling_deliveries(sent_logs, now=taipei_now)
    if initial_24h >= QUOTA_CIRCUIT_BREAKER:
        print(f"🛑 CIRCUIT BREAKER ACTIVE: 24h dispatches ({initial_24h}) >= {QUOTA_CIRCUIT_BREAKER}. Halting to protect Gmail account.")
        check_and_alert_quota(sent_logs, mail_user=mail_user, mail_pass=mail_pass, dry_run=dry_run, subscriber_count=len(subscribers), now=taipei_now)
        update_data_json_quota(data, initial_24h, taipei_now)
        if not dry_run:
            save_json_file(SENT_LOG_FILE, sent_logs)
        return 0
    elif initial_24h >= QUOTA_WARN_THRESHOLD:
        check_and_alert_quota(sent_logs, mail_user=mail_user, mail_pass=mail_pass, dry_run=dry_run, subscriber_count=len(subscribers), now=taipei_now)

    print(f"Loaded {len(subscribers)} subscribers. Checking {len(tenders)} tenders and {len(forecasts)} forecasts (24h sent so far: {initial_24h}/{GMAIL_DAILY_LIMIT})...")
    sent_count = 0
    new_fingerprints = {}

    for sub in subscribers:
        email = sub.get("email", "").strip()
        if not email:
            continue

        # In-loop Circuit Breaker check
        curr_24h, _ = clean_and_count_rolling_deliveries(sent_logs, now=taipei_now)
        if curr_24h >= QUOTA_CIRCUIT_BREAKER:
            print(f"🛑 CIRCUIT BREAKER TRIGGERED during dispatch ({curr_24h}/{GMAIL_DAILY_LIMIT}). Halting immediately.")
            check_and_alert_quota(sent_logs, mail_user=mail_user, mail_pass=mail_pass, dry_run=dry_run, subscriber_count=len(subscribers), now=taipei_now)
            break

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
                log_email_delivery(sent_logs, email, delivery_type="welcome_test", dry_run=True, now=taipei_now)
            else:
                success = send_welcome_email(
                    email,
                    cities=sub.get("cities", ["全部"]),
                    mail_user=mail_user,
                    mail_pass=mail_pass,
                    sample_tenders=tenders,
                    categories=sub.get("categories", ["copier", "forecast"]),
                    sample_forecasts=forecasts
                )
                if success:
                    new_fingerprints[welcome_key] = {
                        "email": email,
                        "type": "welcome_test",
                        "sent_at": taipei_now.strftime("%Y-%m-%d %H:%M:%S")
                    }
                    log_email_delivery(sent_logs, email, delivery_type="welcome_test", dry_run=False, now=taipei_now)
                    check_and_alert_quota(sent_logs, mail_user=mail_user, mail_pass=mail_pass, dry_run=dry_run, subscriber_count=len(subscribers), now=taipei_now)

        matching_tenders = match_tenders_for_subscriber(sub, tenders, sent_logs)
        matching_forecasts = match_forecasts_for_subscriber(sub, forecasts, sent_logs)
        if not matching_tenders and not matching_forecasts:
            continue

        if matching_tenders and matching_forecasts:
            subject = f"【互盛情報】今日通報：{len(matching_tenders)} 筆新標案 · {len(matching_forecasts)} 筆換約預警 ({taipei_date_str})"
        elif matching_tenders:
            subject = f"【互盛情報】今日新增 {len(matching_tenders)} 筆關注標案通報 ({taipei_date_str})"
        else:
            subject = f"【互盛情報】未來換約預警：{len(matching_forecasts)} 筆推測上架標案 ({taipei_date_str})"

        html_body = build_email_html(email, matching_tenders, taipei_date_str, forecasts=matching_forecasts)

        print(f"Sending alert to {email} ({len(matching_tenders)} tenders, {len(matching_forecasts)} forecasts matching {sub.get('cities', '全部')})...")

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
            for fc in matching_forecasts:
                fp = generate_forecast_fingerprint(email, fc)
                new_fingerprints[fp] = {
                    "email": email,
                    "forecast_id": fc.get("id"),
                    "title": fc.get("predicted_title"),
                    "sent_at": taipei_now.strftime("%Y-%m-%d %H:%M:%S"),
                    "dry_run": True
                }
            sent_count += 1
            log_email_delivery(sent_logs, email, delivery_type="digest", dry_run=True, now=taipei_now)
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
                for fc in matching_forecasts:
                    fp = generate_forecast_fingerprint(email, fc)
                    new_fingerprints[fp] = {
                        "email": email,
                        "forecast_id": fc.get("id"),
                        "title": fc.get("predicted_title"),
                        "sent_at": taipei_now.strftime("%Y-%m-%d %H:%M:%S")
                    }
                sent_count += 1
                log_email_delivery(sent_logs, email, delivery_type="digest", dry_run=False, now=taipei_now)
                check_and_alert_quota(sent_logs, mail_user=mail_user, mail_pass=mail_pass, dry_run=dry_run, subscriber_count=len(subscribers), now=taipei_now)
                print(f"Successfully delivered alert to {email}.")
            except Exception as e:
                print(f"Error sending to {email}: {e}")

    final_24h, _ = clean_and_count_rolling_deliveries(sent_logs, now=taipei_now)
    update_data_json_quota(data, final_24h, taipei_now)

    if not dry_run and new_fingerprints:
        sent_logs.update(new_fingerprints)
        save_json_file(SENT_LOG_FILE, sent_logs)
        print(f"Recorded {len(new_fingerprints)} new notification fingerprints in {SENT_LOG_FILE}.")
    elif not dry_run:
        save_json_file(SENT_LOG_FILE, sent_logs)

    return sent_count


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Send email alerts for Ricoh Intel Hub tenders.")
    parser.add_argument("--dry-run", action="store_true", help="Simulate without actually sending emails or modifying sent_notifications.json")
    parser.add_argument("--test-email", type=str, help="Send a test alert email to a specific address")
    parser.add_argument("--send-welcome", type=str, help="Send a welcome test email to a specific address to verify mailbox reception")
    parser.add_argument("--unsubscribe", type=str, help="Unsubscribe an email address from alert notifications")
    parser.add_argument("--check-quota", action="store_true", help="Display rolling 24h Gmail quota usage and check alert status")
    parser.add_argument("--test-quota-alert", action="store_true", help="Force send a test quota alert to admin email to verify template and delivery")
    args = parser.parse_args()

    if args.unsubscribe:
        ok = unsubscribe_email(args.unsubscribe)
        sys.exit(0 if ok else 1)

    dispatched = dispatch_alerts(
        dry_run=args.dry_run,
        test_email=args.test_email,
        send_welcome_to=args.send_welcome,
        check_quota_only=args.check_quota,
        test_quota_alert=args.test_quota_alert
    )
    if not args.check_quota and not args.test_quota_alert:
        print(f"Alert dispatch completed. Total subscribers notified: {dispatched}")
