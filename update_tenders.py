# -*- coding: utf-8 -*-
import urllib.request
import urllib.parse
import argparse
import json
import re
import html
import ssl
from datetime import datetime, timezone, timedelta
import os
import time
from concurrent.futures import ThreadPoolExecutor

OFFICIAL_AWARD_SEARCH_URL = "https://web.pcc.gov.tw/prkms/tender/common/agent/readTenderAgent"
API_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/138.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.7",
    "Referer": "https://pcc-api.openfun.app/"
}
OFFICIAL_SSL_CONTEXT = ssl.create_default_context()
if hasattr(ssl, "VERIFY_X509_STRICT"):
    OFFICIAL_SSL_CONTEXT.verify_flags &= ~ssl.VERIFY_X509_STRICT

def get_city(unit_name):
    cities = ["台北市", "新北市", "桃園市", "台中市", "台南市", "高雄市", 
              "基隆市", "新竹市", "嘉義市", "新竹縣", "苗栗縣", "彰化縣", 
              "南投縣", "雲林縣", "嘉義縣", "屏東縣", "宜蘭縣", "花蓮縣", 
              "台東縣", "澎湖縣", "金門縣", "連江縣"]
    normalized = unit_name.replace("臺", "台")
    for city in cities:
        norm_city = city.replace("臺", "台")
        if norm_city[:2] in normalized:
            return city
    # Special fallbacks
    if "中央大學" in unit_name: return "桃園市"
    if "中興大學" in unit_name: return "台中市"
    if "台灣大學" in unit_name or "臺灣大學" in unit_name: return "台北市"
    if "成功大學" in unit_name: return "台南市"
    if "中山大學" in unit_name: return "高雄市"
    return "台北市"

def extract_budget_and_award(detail):
    budget_val = 0
    award_val = 0
    
    for k, v in detail.items():
        if ("預算" in k or "採購金額" in k) and "金額" in k and "remind" not in k:
            digits = re.findall(r'\d+', str(v).replace(',', ''))
            if digits:
                budget_val = int(digits[0])
                break
                
    for k, v in detail.items():
        if "決標" in k and "總決標金額" in k and "remind" not in k:
            digits = re.findall(r'\d+', str(v).replace(',', ''))
            if digits:
                award_val = int(digits[0])
                break
                
    if budget_val == 0:
        for k, v in detail.items():
            if ("預算" in k or "採購金額" in k) and "remind" not in k:
                digits = re.findall(r'\d+', str(v).replace(',', ''))
                if digits:
                    budget_val = int(digits[0])
                    break
                    
    if award_val == 0:
        for k, v in detail.items():
            if ("決標金額" in k or "中標金額" in k) and "remind" not in k:
                digits = re.findall(r'\d+', str(v).replace(',', ''))
                if digits:
                    award_val = int(digits[0])
                    break
                    
    return budget_val, award_val

def extract_dates(detail, publish_fallback_str):
    publish_date = ""
    deadline_date = ""
    
    # 1. Look for Notice Date (公告日期)
    for k, v in detail.items():
        if "公告日" in k and "remind" not in k and v:
            val = str(v).strip()
            digits = re.findall(r'\d+', val)
            if len(digits) >= 3:
                try:
                    roc_year = int(digits[0])
                    ad_year = roc_year + 1911 if roc_year < 1911 else roc_year
                    publish_date = f"{ad_year}-{int(digits[1]):02d}-{int(digits[2]):02d}"
                    break
                except:
                    pass
                    
    # 2. Look for Bidding Deadline (截止投標)
    for k, v in detail.items():
        if ("截止" in k or "收件" in k) and ("投標" in k or "收件" in k) and "remind" not in k and v:
            val = str(v).strip()
            digits = re.findall(r'\d+', val)
            if len(digits) >= 3:
                try:
                    roc_year = int(digits[0])
                    ad_year = roc_year + 1911 if roc_year < 1911 else roc_year
                    deadline_date = f"{ad_year}-{int(digits[1]):02d}-{int(digits[2]):02d}"
                    break
                except:
                    pass
                    
    if not publish_date and publish_fallback_str:
        if len(publish_fallback_str) == 8:
            try:
                dt = datetime.strptime(publish_fallback_str, "%Y%m%d")
                publish_date = dt.strftime("%Y-%m-%d")
            except:
                pass
                
    if not deadline_date and publish_date:
        try:
            dt = datetime.strptime(publish_date, "%Y-%m-%d")
            deadline_date = (dt + timedelta(days=14)).strftime("%Y-%m-%d")
        except:
            pass
            
    return publish_date, deadline_date

def extract_winning_competitor(detail):
    winner = ""
    companies = {}
    for k, v in detail.items():
        match_name = re.fullmatch(r'投標廠商:投標廠商(\d+):廠商名稱', k)
        if match_name:
            companies[match_name.group(1)] = str(v).strip()

    for k, v in detail.items():
        match_won = re.fullmatch(r'投標廠商:投標廠商(\d+):是否得標', k)
        if match_won and str(v).strip() in ["是", "得標"]:
            winner = companies.get(match_won.group(1), "")
            if winner:
                break

    if not winner:
        for k, v in detail.items():
            if (k.endswith(":得標廠商") or k.endswith(":得標廠商名稱")) and v:
                val = str(v).strip()
                if val and len(val) > 2 and "中華民國" not in val:
                    winner = val
                    break
                    
    return winner

def map_competitor_name(raw_name):
    if not raw_name:
        return ""
    name = raw_name.replace(" ", "")
    
    if any(x in name for x in ["互盛", "理光", "RICOH", "Ricoh"]):
        return "本公司 (互盛 RICOH)"
        
    if any(x in name for x in ["富士", "FUJIFILM", "Fujifilm", "全錄", "Xerox"]):
        return "富士軟片 (FUJIFILM)"
    if any(x in name for x in ["佳能", "Canon", "canon"]):
        return "台灣佳能 (Canon)"
    if any(x in name for x in ["金儀", "Konica", "Minolta", "美能達"]):
        return "金儀 Konica Minolta"
    if any(x in name for x in ["震旦", "SHARP", "Sharp", "夏普"]):
        return "震旦 SHARP"
    if any(x in name for x in ["京瓷", "Kyocera", "kyocera"]):
        return "台灣京瓷 (Kyocera)"
    if any(x in name for x in ["愛普生", "Epson", "epson"]):
        return "台灣愛普生 (Epson)"
    if any(x in name for x in ["惠普", "HP", "hp"]):
        return "台灣惠普 (HP)"
    if any(x in name for x in ["兄弟", "Brother", "brother"]):
        return "台灣兄弟 (Brother)"
        
    return raw_name

def parse_contract_duration(title):
    title_norm = title.replace("臺", "台")
    match_years = re.search(r'(\d+)\s*(?:~|至|-)\s*(\d+)\s*年', title_norm)
    if match_years:
        start_yr = int(match_years.group(1))
        end_yr = int(match_years.group(2))
        if start_yr < 125 and end_yr < 125 and end_yr >= start_yr:
            return max(1, end_yr - start_yr + 1)
            
    match_months = re.search(r'(\d+)\s*(?:個)?月', title_norm)
    if match_months:
        months = int(match_months.group(1))
        if not re.search(rf'{months}\s*月\s*\d+\s*日', title_norm):
            return max(1, months // 12)
            
    match_num_years = re.search(r'(\d+)\s*年', title_norm)
    if match_num_years:
        val = int(match_num_years.group(1))
        if 100 <= val <= 125:
            matches = re.findall(r'(\d+)\s*年', title_norm)
            for m in matches:
                m_val = int(m)
                if m_val < 10:
                    return m_val
        else:
            if val < 10:
                return val
                
    if "租" in title_norm:
        return 3
    return 1

def is_relevant_equipment_title(title):
    return classify_tender_relevance({"brief": {"title": title}})["status"] == "included"


DIRECT_EQUIPMENT_TERMS = [
    "影印機", "複印機", "複合機", "數位複合", "彩色複合機", "多功能機", "多功機",
    "多功能複合機", "多功能事務機", "多功能影印", "事務機", "辦公事務機", "印表機",
    "列印機", "雷射印表機", "噴墨印表機", "點陣式印表機", "標籤印表機", "條碼印表機",
    "繪圖機", "大圖輸出機", "數位印刷機", "生產型印刷機", "MFP", "copier", "printer"
]
BROAD_EQUIPMENT_TERMS = [
    "輸出設備", "列印設備", "文件輸出", "辦公設備", "辦公室設備", "事務設備", "資訊設備",
    "電腦週邊", "資訊週邊", "辦公自動化", "文件處理設備", "圖文輸出", "輸出系統",
    "列印系統", "文件管理", "列印管理"
]
DETAIL_SIGNAL_TERMS = [
    "列印", "複印", "影印", "掃描", "傳真", "自動送稿", "網路列印", "雙面列印",
    "每分鐘張數", "基本張數", "計張", "ppm", "cpm", "A3", "A4"
]
CONTRACT_TERMS = ["採購", "購置", "汰換", "更新", "租賃", "租用", "維護", "維修", "保養", "計張", "全包服務", "開口契約"]
MACHINE_TOOL_TERMS = ["車銑複合機", "複合加工機", "車銑", "鑽銑", "CNC", "工具機", "機床", "機械科"]
SUPPLY_TERMS = ["耗材", "碳粉", "墨水", "色帶", "感光鼓", "轉寫帶", "零件"]
PRINT_SERVICE_TERMS = ["印刷服務", "文宣印製", "海報輸出", "影印裝訂", "印刷品製作", "藍晒"]
SPECIALIZED_PRINTING_TERMS = ["3D列印機", "3D印表機", "積層製造設備"]
DOT_MATRIX_PRINTER_TERMS = ["點陣式印表機", "點矩陣印表機"]
PRINTER_TERMS = ["印表機", "列印機", "printer"]
MAINTENANCE_TERMS = ["維護", "維修", "保養"]
CONTRACT_CHANGE_TERMS = ["契約變更", "變更案", "後續擴充", "追加採購"]
NON_TARGET_TERM_GROUPS = {
    "network_or_server": ["機房", "交換器", "無線網路", "網路設備", "網路管理", "伺服器", "儲存設備", "資通訊", "RFID", "課程管理平台"],
    "computer_or_software": ["電腦軟體", "個人電腦", "平板電腦", "資訊科技教室", "電腦教室"],
    "medical_equipment": ["智慧藥櫃", "X光機", "Ｘ光機", "DR數位影像", "醫療設備", "診斷設備"],
    "construction_or_furniture": ["規劃設計監造", "設計監造", "監造技術服務", "輕鋼架", "收納櫃", "裝修工程", "辦公空間改善"],
    "non_office_output": ["氣泡輸出設備", "水處理", "廣播設備", "音響設備", "城鎮韌性演習"],
}
RELEVANT_DETAIL_KEY_TERMS = [
    "標案名稱", "標的名稱", "標的分類", "採購品項", "品項名稱", "品名",
    "規格", "需求說明", "數量摘要", "工作內容", "附加說明"
]


def _matched_terms(text, terms):
    lowered = str(text or "").lower()
    return [term for term in terms if term.lower() in lowered]


def _flatten_detail(detail):
    if not isinstance(detail, dict):
        return ""
    relevant_values = []
    for key, value in detail.items():
        clean_key = re.sub(r"^\d+:", "", str(key))
        if value is not None and any(term in clean_key for term in RELEVANT_DETAIL_KEY_TERMS):
            relevant_values.append(f"{clean_key} {value}")
    return " ".join(relevant_values)


def _non_target_match(text):
    for category, terms in NON_TARGET_TERM_GROUPS.items():
        matched = _matched_terms(text, terms)
        if matched:
            return category, matched
    return "", []


def get_title_scope_exclusion(title):
    contract_change_terms = _matched_terms(title, CONTRACT_CHANGE_TERMS)
    if contract_change_terms:
        return {
            "status": "excluded", "confidence": "high", "score": -4,
            "category": "contract_change", "matched_terms": contract_change_terms,
            "reason": "契約變更或後續擴充不是新的投標機會"
        }
    dot_matrix_terms = _matched_terms(title, DOT_MATRIX_PRINTER_TERMS)
    if dot_matrix_terms:
        return {
            "status": "excluded", "confidence": "high", "score": -4,
            "category": "dot_matrix_printer", "matched_terms": dot_matrix_terms,
            "reason": "點陣式印表機不在追蹤範圍"
        }
    printer_terms = _matched_terms(title, PRINTER_TERMS)
    maintenance_terms = _matched_terms(title, MAINTENANCE_TERMS)
    if printer_terms and maintenance_terms:
        return {
            "status": "excluded", "confidence": "high", "score": -4,
            "category": "printer_maintenance",
            "matched_terms": list(dict.fromkeys(printer_terms + maintenance_terms)),
            "reason": "印表機維護、維修或保養不在追蹤範圍"
        }
    return None


def classify_tender_relevance(item, detail=None):
    """Return an explainable high-recall classification for an announcement."""
    brief = item.get("brief", {}) if isinstance(item, dict) else {}
    title = str(brief.get("title", "")).replace("臺", "台")
    category = str(brief.get("category", ""))
    announcement_type = str(brief.get("type", ""))
    detail_text = _flatten_detail(detail)
    combined = f"{title} {category} {detail_text}"

    machine_terms = _matched_terms(combined, MACHINE_TOOL_TERMS)
    direct_title = _matched_terms(title, DIRECT_EQUIPMENT_TERMS)
    direct_detail = _matched_terms(f"{category} {detail_text}", DIRECT_EQUIPMENT_TERMS)
    broad_terms = _matched_terms(combined, BROAD_EQUIPMENT_TERMS)
    detail_signals = _matched_terms(f"{category} {detail_text}", DETAIL_SIGNAL_TERMS)
    contract_terms = _matched_terms(combined, CONTRACT_TERMS)
    supply_terms = _matched_terms(title, SUPPLY_TERMS)
    service_terms = _matched_terms(title, PRINT_SERVICE_TERMS)
    specialized_terms = _matched_terms(title, SPECIALIZED_PRINTING_TERMS)

    title_exclusion = get_title_scope_exclusion(f"{title} {announcement_type}")
    if title_exclusion:
        return title_exclusion

    if machine_terms:
        return {"status": "excluded", "confidence": "high", "score": -4, "category": "industrial_machine", "matched_terms": machine_terms, "reason": "工業機械誤判"}
    if supply_terms:
        return {"status": "excluded", "confidence": "high", "score": -3, "category": "supplies", "matched_terms": supply_terms, "reason": "耗材或零件"}
    if service_terms and not direct_title:
        return {"status": "excluded", "confidence": "high", "score": -3, "category": "printing_service", "matched_terms": service_terms, "reason": "純印務服務"}
    if specialized_terms:
        return {"status": "excluded", "confidence": "high", "score": -4, "category": "specialized_printing", "matched_terms": specialized_terms, "matched_fields": ["title"], "reason": "3D 或特殊列印設備不在辦公輸出設備範圍"}

    non_target_category, non_target_terms = _non_target_match(f"{title} {category} {detail_text}")
    if non_target_terms and not direct_title and not direct_detail:
        return {
            "status": "excluded", "confidence": "high", "score": -3,
            "category": non_target_category, "matched_terms": non_target_terms,
            "matched_fields": ["title" if _matched_terms(title, non_target_terms) else "detail"],
            "reason": "明確屬於非辦公輸出設備"
        }

    score = (3 if direct_title else 0) + (2 if direct_detail else 0) + (1 if broad_terms else 0) + (1 if detail_signals else 0) + (1 if contract_terms else 0)
    matched = list(dict.fromkeys(direct_title + direct_detail + broad_terms + detail_signals + contract_terms))
    matched_fields = []
    if direct_title or _matched_terms(title, BROAD_EQUIPMENT_TERMS):
        matched_fields.append("title")
    if category and (_matched_terms(category, DIRECT_EQUIPMENT_TERMS) or _matched_terms(category, BROAD_EQUIPMENT_TERMS)):
        matched_fields.append("category")
    if detail_text and (direct_detail or detail_signals):
        matched_fields.append("detail")

    if direct_title or direct_detail:
        return {"status": "included", "confidence": "high" if direct_title else "medium", "score": score, "category": "office_output_equipment", "matched_terms": matched, "matched_fields": matched_fields, "reason": "命中設備名稱或公告規格"}
    if broad_terms:
        return {"status": "review", "confidence": "low", "score": score, "category": "needs_review", "matched_terms": matched, "matched_fields": matched_fields, "reason": "名稱較廣泛，需檢查公告品項或規格"}
    return {"status": "excluded", "confidence": "high", "score": 0, "category": "unrelated", "matched_terms": [], "matched_fields": [], "reason": "未命中設備範圍"}


def deduplicate_announcements(records):
    """Keep the newest announcement version for each agency and tender number."""
    newest_first = sorted(
        (record for record in records if isinstance(record, dict)),
        key=lambda record: (str(record.get("date", "")), str(record.get("filename", ""))),
        reverse=True
    )
    unique_records = []
    seen = set()
    for record in newest_first:
        project_key = (record.get("unit_id", ""), record.get("job_number", ""))
        announcement_type = str(record.get("brief", {}).get("type", ""))
        lifecycle_bucket = "terminal" if "決標" in announcement_type else "active"
        if not all(project_key):
            project_key = (
                record.get("unit_id", ""), record.get("job_number", ""),
                str(record.get("date", "")), record.get("filename", "")
            )
        else:
            project_key = (*project_key, lifecycle_bucket)
        if project_key in seen:
            continue
        seen.add(project_key)
        unique_records.append(record)
    return unique_records

def classify_equipment(title):
    normalized = title.replace("臺", "台")
    if any(word in normalized for word in ["點陣式印表機", "點矩陣印表機"]):
        return "dot_matrix_printer"
    if any(word in normalized for word in ["影印機", "複印機", "複合機", "多功能機"]):
        return "copier"
    if "印表機" in normalized:
        mixed_it_words = ["電腦", "螢幕", "監視器", "軟體", "網路", "伺服器"]
        return "mixed_it_equipment" if any(word in normalized for word in mixed_it_words) else "printer"
    if "事務機" in normalized:
        return "office_machine"
    return ""

def classify_contract(title):
    if any(word in title for word in ["租賃", "租用", "出租"]):
        return "rental"
    if any(word in title for word in ["維護", "維修", "保養"]):
        return "maintenance"
    if any(word in title for word in ["採購", "購置", "汰換", "新購", "更新"]):
        return "purchase"
    return "unspecified"

def is_comparable_history(current_title, history_title):
    current_equipment = classify_equipment(current_title)
    history_equipment = classify_equipment(history_title)
    return (
        bool(current_equipment)
        and current_equipment == history_equipment
        and classify_contract(current_title) == classify_contract(history_title)
    )

def history_scope_key(unit_id, title):
    return (
        f"{unit_id}|{classify_equipment(title)}|{classify_contract(title)}|"
        f"{build_history_title_query(title)}"
    )

def build_history_title_query(title):
    normalized = re.sub(r'[「」『』【】()]', '', title).strip()
    year_suffix = re.split(r'(?:\d{2,3}(?:\s*[-~至]\s*\d{2,3})?\s*)?年度', normalized, maxsplit=1)
    if len(year_suffix) > 1 and year_suffix[-1].strip():
        normalized = year_suffix[-1].strip()
    normalized = re.sub(r'\d+\s*(?:式|台|臺|部|組|套|批)$', '', normalized).strip()
    return normalized

def history_cutoff_date(years=5):
    today = datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=8))).date()
    try:
        return today.replace(year=today.year - years)
    except ValueError:
        return today.replace(year=today.year - years, day=28)

def is_recent_history(record, years=5):
    try:
        return datetime.strptime(record.get("award_date", ""), "%Y-%m-%d").date() >= history_cutoff_date(years)
    except (TypeError, ValueError):
        return False

def exclude_contract_changes(records):
    explicit_change_words = ["契約變更", "變更案", "後續擴充", "追加採購"]
    base_records = {
        record.get("job_number", ""): record
        for record in records
        if record.get("job_number")
    }
    filtered = []
    for record in records:
        title = record.get("title", "")
        if any(word in title for word in explicit_change_words):
            continue
        variant_match = re.fullmatch(r'(.+)-\d+', record.get("job_number", ""))
        if variant_match:
            base_record = base_records.get(variant_match.group(1))
            if base_record and is_comparable_history(title, base_record.get("title", "")):
                continue
        filtered.append(record)
    return filtered

def get_related_units(unit_id, unit_name, unit_map):
    if not unit_id or "." not in unit_id or not isinstance(unit_map, dict):
        return {}
    parent_id = unit_id.rsplit(".", 1)[0]
    parent_name = unit_map.get(parent_id, "")
    normalized_unit = unit_name.replace("臺", "台")
    normalized_parent = parent_name.replace("臺", "台")
    if (
        not parent_name
        or not normalized_unit.startswith(normalized_parent)
        or normalized_unit == normalized_parent
        or normalized_parent.endswith(("政府", "行政院", "司法院", "監察院", "考試院", "立法院", "部"))
    ):
        return {}

    parent_depth = parent_id.count(".")
    return {
        candidate_id: candidate_name
        for candidate_id, candidate_name in unit_map.items()
        if (
            (candidate_id == parent_id or (
                candidate_id.startswith(parent_id + ".")
                and candidate_id.count(".") == parent_depth + 1
            ))
            and candidate_name.replace("臺", "台").startswith(normalized_parent)
        )
    }

def looks_like_country(value):
    country_names = ["美國", "新加坡", "日本", "德國", "英國", "中國", "加拿大", "法國", "澳大利亞", "韓國"]
    return any(str(value).startswith(country) for country in country_names)

def date_to_iso(raw_date):
    value = str(raw_date or "")
    if len(value) == 8:
        try:
            return datetime.strptime(value, "%Y%m%d").strftime("%Y-%m-%d")
        except ValueError:
            pass
    return ""

def median(values):
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2

def verify_official_award_notice(unit_id, job_number, award_date, max_retries=2):
    if not unit_id or not job_number or len(award_date) < 4:
        return False

    year = award_date[:4]
    params = {
        "pageSize": "10",
        "firstSearch": "false",
        "isQuery": "true",
        "isBinding": "N",
        "isLogIn": "N",
        "orgName": "",
        "orgId": unit_id,
        "tenderName": "",
        "tenderId": job_number,
        "tenderStatus": "TENDER_STATUS_1",
        "tenderWay": "TENDER_WAY_ALL_DECLARATION",
        "awardAnnounceStartDate": f"{year}/01/01",
        "awardAnnounceEndDate": f"{year}/12/31",
        "radProctrgCate": "",
        "tenderRange": "",
        "item": "",
        "gottenVendorName": "",
        "gottenVendorId": "",
        "submitVendorName": "",
        "submitVendorId": "",
        "execLocation": "",
        "priorityCate": "",
        "radReConstruct": "",
        "policyAdvocacy": "",
        "isCpp": ""
    }
    query_url = f"{OFFICIAL_AWARD_SEARCH_URL}?{urllib.parse.urlencode(params)}"
    request = urllib.request.Request(query_url, headers={"User-Agent": "Mozilla/5.0"})

    for attempt in range(max_retries):
        try:
            with urllib.request.urlopen(request, timeout=30, context=OFFICIAL_SSL_CONTEXT) as response:
                page = html.unescape(response.read().decode("utf-8", errors="replace"))
            no_results = re.search(r'共有\s*<span[^>]*>\s*0\s*</span>\s*筆資料', page)
            return not no_results and job_number in page
        except Exception as error:
            if attempt + 1 == max_retries:
                print(f"Official award verification failed for {unit_id}/{job_number}: {error}")
                return False
            time.sleep(2)

    return False

def fetch_tender_detail_with_retry(unit_id, job_number, max_retries=3):
    encoded_job = urllib.parse.quote(job_number)
    detail_api_url = f"https://pcc-api.openfun.app/api/tender?unit_id={unit_id}&job_number={encoded_job}"
    req_detail = urllib.request.Request(detail_api_url, headers=API_HEADERS)
    
    for attempt in range(max_retries):
        try:
            with urllib.request.urlopen(req_detail) as res_detail:
                return json.loads(res_detail.read().decode('utf-8'))
        except urllib.error.HTTPError as e:
            if e.code == 429:
                wait_time = (attempt + 1) * 3
                print(f"Received 429 Too Many Requests. Retrying in {wait_time} seconds (attempt {attempt+1}/{max_retries})...")
                time.sleep(wait_time)
            else:
                print(f"HTTP Error {e.code} when fetching detail: {e}")
                break
        except Exception as e:
            if attempt + 1 < max_retries:
                wait_time = (attempt + 1) * 2
                print(f"Detail request failed. Retrying in {wait_time} seconds: {e}")
                time.sleep(wait_time)
            else:
                print(f"Error fetching detail after {max_retries} attempts: {e}")
            
    return None

def fetch_json_with_retry(url, label, max_retries=5):
    request = urllib.request.Request(url, headers=API_HEADERS)
    for attempt in range(max_retries):
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                payload = response.read().decode('utf-8')
            try:
                return json.loads(payload)
            except json.JSONDecodeError:
                # The source sometimes emits PHP warnings before a valid empty
                # JSON object on dates with no announcements.
                json_start = payload.rfind("\n{")
                if json_start >= 0:
                    return json.loads(payload[json_start + 1:])
                raise
        except urllib.error.HTTPError as error:
            if error.code != 429 or attempt + 1 == max_retries:
                print(f"{label} failed: {error}")
                return None
            wait_time = (attempt + 1) * 5
            print(f"{label} rate limited. Retrying in {wait_time} seconds...")
            time.sleep(wait_time)
        except Exception as error:
            if attempt + 1 == max_retries:
                print(f"{label} failed after {max_retries} attempts: {error}")
                return None
            wait_time = (attempt + 1) * 3
            print(f"{label} failed. Retrying in {wait_time} seconds: {error}")
            time.sleep(wait_time)
    return None

def build_required_dates(mode, today, collection_days):
    if mode == "live":
        return [today, today - timedelta(days=1)]
    for days_ago in range(2, 61):
        backfill_date = today - timedelta(days=days_ago)
        if collection_days.get(backfill_date.strftime("%Y-%m-%d"), {}).get("status") != "complete":
            return [backfill_date]
    return []


def main(mode="live"):
    if mode not in ("live", "maintenance"):
        raise ValueError(f"Unsupported update mode: {mode}")
    print(f"Starting tender updater in {mode} mode...")
    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_path = os.path.join(script_dir, "data.json")
    existing_data = {}
    existing_history_by_unit = {}
    history_unit_names = {}
    history_unit_refresh = {}
    history_deep_refresh = {}
    candidate_cache = []
    collection_days = {}
    refresh_date = datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=8))).strftime("%Y-%m-%d")

    try:
        with open(output_path, "r", encoding="utf-8") as existing_file:
            existing_data = json.load(existing_file)
        history_unit_refresh = dict(existing_data.get("history_unit_refresh", {}))
        history_deep_refresh = dict(existing_data.get("history_deep_refresh", {}))
        candidate_cache = list(existing_data.get("candidate_cache", []))
        collection_days = dict(existing_data.get("collection_days", {}))

        cached_records = list(existing_data.get("history_cache", []))
        for tender in existing_data.get("tenders", []):
            unit_id = tender.get("unit_id", "")
            unit_name = tender.get("unit", "")
            for record in tender.get("history_records", []):
                cached_records.append({
                    "unit_id": record.get("source_unit_id", unit_id),
                    "unit_name": record.get("source_unit", unit_name),
                    **record
                })

        for cached in cached_records:
            unit_id = cached.get("unit_id", "")
            unit_name = cached.get("unit_name", "")
            job_number = cached.get("job_number", "")
            if not unit_id or not job_number or cached.get("official_verified") is not True:
                continue
            history_unit_names[unit_id] = unit_name
            history_record = {
                key: value for key, value in cached.items()
                if key not in ("unit_id", "unit_name", "source_unit_id", "source_unit", "relation_scope", "is_stale")
            }
            existing_history_by_unit.setdefault(unit_id, {})[job_number] = history_record
        print(f"Loaded {sum(len(records) for records in existing_history_by_unit.values())} verified cached histories.")
    except (FileNotFoundError, json.JSONDecodeError) as error:
        print(f"No usable history cache found: {error}")

    taipei_now = datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=8)))
    today = taipei_now.date()
    required_dates = build_required_dates(mode, today, collection_days)

    # The date endpoint returns the day's entire announcement set. Keep every
    # potentially relevant record so later classification rules can re-evaluate it.
    raw_active_tenders = list(candidate_cache)
    successful_dates = []
    failed_dates = []
    for scan_date in required_dates:
        compact_date = scan_date.strftime("%Y%m%d")
        iso_date = scan_date.strftime("%Y-%m-%d")
        url = f"https://pcc-api.openfun.app/api/listbydate?date={compact_date}"
        day_data = fetch_json_with_retry(url, f"daily announcement census {iso_date}")
        if day_data == {} and scan_date < today:
            day_data = {"records": []}
        if not isinstance(day_data, dict) or not isinstance(day_data.get("records"), list):
            failed_dates.append(iso_date)
            if collection_days.get(iso_date, {}).get("status") != "complete":
                collection_days[iso_date] = {
                    "status": "incomplete", "source_records": 0, "candidate_records": 0,
                    "review_records": 0, "checked_at": taipei_now.strftime("%Y-%m-%d %H:%M")
                }
            continue

        day_records = day_data["records"]
        day_candidates = []
        for record in day_records:
            classification = classify_tender_relevance(record)
            if classification["status"] not in ("included", "review"):
                continue
            day_candidates.append({**record, "relevance": classification})
        day_candidates = deduplicate_announcements(day_candidates)
        review_count = sum(
            1 for candidate in day_candidates
            if candidate.get("relevance", {}).get("status") == "review"
        )

        raw_active_tenders = [record for record in raw_active_tenders if str(record.get("date", "")) != compact_date]
        raw_active_tenders.extend(day_candidates)
        collection_days[iso_date] = {
            "status": "complete",
            "source_records": len(day_records),
            "candidate_records": len(day_candidates),
            "review_records": review_count,
            "checked_at": taipei_now.strftime("%Y-%m-%d %H:%M")
        }
        successful_dates.append(iso_date)
        print(f"Census {iso_date}: {len(day_records)} announcements, {len(day_candidates)} equipment candidates, {review_count} need review.")
        time.sleep(1)

    cutoff_compact = (today - timedelta(days=60)).strftime("%Y%m%d")
    raw_active_tenders = [record for record in raw_active_tenders if str(record.get("date", "")) >= cutoff_compact]
    raw_active_tenders = [
        record for record in raw_active_tenders
        if classify_tender_relevance(record)["status"] in ("included", "review")
    ]
    raw_active_tenders = deduplicate_announcements(raw_active_tenders)
    collection_days = {
        day: summary for day, summary in collection_days.items()
        if day >= (today - timedelta(days=60)).strftime("%Y-%m-%d")
    }

    today_iso = today.strftime("%Y-%m-%d")
    if mode == "live" and today_iso in failed_dates:
        print("Today's census failed. Preserving the last verified database and recording the failed attempt.")
        existing_status = dict(existing_data.get("collection_status", {}))
        existing_status.update({
            "latest_attempt_status": "failed",
            "latest_attempt_at": taipei_now.strftime("%Y-%m-%d %H:%M"),
            "failed_dates": failed_dates
        })
        existing_data["collection_status"] = existing_status
        with open(output_path, "w", encoding="utf-8") as output_file:
            json.dump(existing_data, output_file, ensure_ascii=False, indent=2)
        return
        
    # Filter and identify active tenders and their units
    active_tenders = []
    seen_active_projects = set()
    active_units_dict = {}
    review_candidates = []
    prefetched_details = {}
    
    raw_active_sorted = sorted(
        raw_active_tenders, 
        key=lambda x: int(x.get("date", 0)) if isinstance(x, dict) and x.get("date") else 0, 
        reverse=True
    )
    
    for item in raw_active_sorted:
        if not isinstance(item, dict):
            continue
            
        filename = item.get("filename", "")
        brief = item.get("brief", {})
        title = brief.get("title", "") or ""
        brief_type = brief.get("type", "") or ""
        unit_name = item.get("unit_name", "") or ""
        date_raw = str(item.get("date", ""))
        unit_id = item.get("unit_id", "")
        
        # 1. STRICT ACTIVE FILTER: Exclude resolved/failed from active list
        if "\u6c7a\u6a19" in brief_type or "\u7121\u6cd5\u6c7a\u6a19" in brief_type:
            continue
            
        # 2. Keep a rolling 60-day opportunity window.
        if not date_raw.isdigit() or date_raw < cutoff_compact:
            continue
            
        # 3. Skip Bank of Taiwan central procurement
        if "\u81fa\u7063\u9280\u884c" in unit_name or "\u53f0\u7063\u9280\u884c" in unit_name:
            continue
            
        # 4. Use an explainable multi-layer classification.
        title_norm = title.replace("\u81fa", "\u53f0")
        relevance = classify_tender_relevance(item)
        item["relevance"] = relevance
            
        # 5. Skip duplicates
        project_key = (unit_id, item.get("job_number", ""), date_raw, filename)
        lifecycle_key = (unit_id, item.get("job_number", ""))
        if lifecycle_key in seen_active_projects:
            continue
            
        # 6. Keep definite matches and broad terms that still need detail inspection.
        if relevance["status"] not in ("included", "review"):
            continue

        seen_active_projects.add(lifecycle_key)

        if relevance["status"] == "review":
            detail_data = fetch_tender_detail_with_retry(unit_id, item.get("job_number", ""))
            merged_detail = {}
            if detail_data and detail_data.get("records"):
                for record_index, record in enumerate(detail_data["records"]):
                    for key, value in record.get("detail", {}).items():
                        merged_detail[f"{record_index}:{key}"] = value
            detailed_relevance = classify_tender_relevance(item, merged_detail)
            if not detail_data or not detail_data.get("records"):
                review_candidates.append({
                    "date": date_to_iso(date_raw), "title": title, "unit": unit_name,
                    "unit_id": unit_id, "job_number": item.get("job_number", ""),
                    "tender_url": f"https://web.pcc.gov.tw/prkms/tender/common/noticeDate/redirectPublic?ds={date_raw}&fn={filename}.xml",
                    "relevance": {**detailed_relevance, "reason": "政府公告明細暫時無法取得，等待下次自動查驗"}
                })
            if detailed_relevance["status"] != "included":
                continue
            relevance = detailed_relevance
            item["relevance"] = relevance
            prefetched_details[project_key] = detail_data
            
        active_tenders.append(item)
        active_units_dict[unit_name] = unit_id
        
    print(f"Identified {len(active_tenders)} active/recent tenders from {len(active_units_dict)} units.")
    
    failed_history_units = []
    queried_history_unit_ids = set()
    unit_total_pages = {}

    def fetch_unit_history(
        h_unit_id,
        h_unit,
        comparable_titles=None,
        recent_only=False,
        request_delay=1,
        start_page=1,
        scan_all_pages=False,
        deep_refresh_keys=None
    ):
        if not h_unit_id:
            return []
        queried_history_unit_ids.add(h_unit_id)
        results = []
        page = start_page
        scan_completed = True
        while True:
            url_unit = f"https://pcc-api.openfun.app/api/listbyunit?unit_id={h_unit_id}&page={page}"
            data_unit = fetch_json_with_retry(
                url_unit,
                f"listbyunit page {page} for '{h_unit}' ({h_unit_id})"
            )
            if data_unit is None:
                failed_history_units.append(h_unit)
                scan_completed = False
                print(f"Keeping cached award history for '{h_unit}' and continuing.")
                break

            total_pages = max(1, int(data_unit.get("total_page", 1) or 1))
            unit_total_pages[h_unit_id] = total_pages
            for record in data_unit.get("records", []):
                if not isinstance(record, dict):
                    continue
                brief = record.get("brief", {})
                notice_type = brief.get("type", "")
                if "決標" not in notice_type or "無法決標" in notice_type:
                    continue
                history_title = brief.get("title", "")
                if not is_relevant_equipment_title(history_title):
                    continue
                if comparable_titles and not any(is_comparable_history(title, history_title) for title in comparable_titles):
                    continue
                if recent_only and str(record.get("date", "")) < history_cutoff_date().strftime("%Y%m%d"):
                    continue
                record["unit_name"] = h_unit
                results.append(record)

            if not scan_all_pages or page >= total_pages:
                break
            page += 1
            time.sleep(request_delay)

        if scan_completed:
            history_unit_refresh[h_unit_id] = refresh_date
            if scan_all_pages:
                for scope_key in deep_refresh_keys or [h_unit_id]:
                    history_deep_refresh[scope_key] = refresh_date
        time.sleep(request_delay)
        return results

    def fetch_title_history(h_unit_id, h_unit, title):
        query = build_history_title_query(title)
        if len(query) < 6:
            print(f"Skipped overly broad history title search '{query}' for '{h_unit}'.")
            return [], False
        results = []
        page = 1
        scan_completed = True
        while True:
            encoded_query = urllib.parse.quote(query)
            url = f"https://pcc-api.openfun.app/api/searchbytitle?query={encoded_query}&page={page}"
            data = fetch_json_with_retry(url, f"history title search '{query}' page {page}")
            if data is None:
                scan_completed = False
                break
            total_pages = max(1, int(data.get("total_pages", 1) or 1))
            for record in data.get("records", []):
                if not isinstance(record, dict) or record.get("unit_id") != h_unit_id:
                    continue
                brief = record.get("brief", {})
                notice_type = brief.get("type", "")
                history_title = brief.get("title", "")
                if (
                    "決標" not in notice_type
                    or "無法決標" in notice_type
                    or not is_comparable_history(title, history_title)
                ):
                    continue
                record["unit_name"] = h_unit
                results.append(record)
            if page >= total_pages:
                break
            if page >= 15:
                print(f"Stopped broad history title search '{query}' after 15 pages; cached results were preserved.")
                scan_completed = False
                break
            page += 1
            time.sleep(1)
        return results, scan_completed

    history_pool = {
        unit: list(existing_history_by_unit.get(unit_id, {}).values())
        for unit, unit_id in active_units_dict.items()
    }
    seen_history_jobs = set()

    def process_history_items(raw_items):
        for h_item in sorted(raw_items, key=lambda item: int(item.get("date", 0)), reverse=True):
            h_unit = h_item.get("unit_name", "")
            h_unit_id = h_item.get("unit_id", "")
            h_job = h_item.get("job_number", "")
            job_key = (h_unit_id, h_job)
            if not h_unit_id or not h_job or job_key in seen_history_jobs:
                continue
            seen_history_jobs.add(job_key)

            cached_history = existing_history_by_unit.get(h_unit_id, {}).get(h_job)
            if cached_history and not looks_like_country(cached_history.get("winner", "")):
                continue

            h_details = fetch_tender_detail_with_retry(h_unit_id, h_job)
            if not h_details or not h_details.get("records"):
                continue
            award_records = [
                record for record in h_details["records"]
                if "決標" in record.get("brief", {}).get("type", "")
                and "無法決標" not in record.get("brief", {}).get("type", "")
            ]
            if not award_records:
                continue
            h_award_record = max(award_records, key=lambda record: int(record.get("date", 0)))
            h_detail_obj = h_award_record.get("detail", {})
            h_budget, h_award = extract_budget_and_award(h_detail_obj)
            if h_budget <= 0 or h_award <= 0:
                continue

            h_winner = extract_winning_competitor(h_detail_obj)
            h_date = date_to_iso(h_award_record.get("date"))
            if not verify_official_award_notice(h_unit_id, h_job, h_date):
                print(f"Skipped unverified history: {h_unit} | {h_date} | {h_job}")
                continue
            discount_rate = (h_award / h_budget) * 100
            history_record = {
                "award_date": h_date,
                "year": int(h_date[:4]) if h_date else None,
                "title": h_award_record.get("brief", {}).get("title", h_item.get("brief", {}).get("title", "")),
                "job_number": h_job,
                "budget": h_budget,
                "award_price": h_award,
                "discount_rate": round(discount_rate, 1) if 0 < discount_rate <= 100 else None,
                "winner": map_competitor_name(h_winner) if h_winner else "未公開",
                "source_url": h_detail_obj.get("url", ""),
                "official_verified": True,
                "verification_source": "政府電子採購網決標查詢"
            }
            history_pool.setdefault(h_unit, [])
            history_pool[h_unit] = [
                record for record in history_pool[h_unit]
                if record.get("job_number") != h_job
            ]
            history_pool[h_unit].append(history_record)
            existing_history_by_unit.setdefault(h_unit_id, {})[h_job] = history_record
            history_unit_names[h_unit_id] = h_unit
            print(f"Saved verified history: {h_unit} | {h_date} | {h_job} | Budget {h_budget} | Award {h_award}")

    print("Querying complete award history for all active agencies...")
    direct_history_items = []
    for h_unit, h_unit_id in active_units_dict.items():
        direct_history_items.extend(fetch_unit_history(h_unit_id, h_unit))
    process_history_items(direct_history_items)

    titles_by_unit_id = {}
    for item in active_tenders:
        titles_by_unit_id.setdefault(item.get("unit_id", ""), []).append(item.get("brief", {}).get("title", ""))

    deep_history_items = []
    for h_unit, h_unit_id in active_units_dict.items():
        if unit_total_pages.get(h_unit_id, 1) <= 1:
            continue
        missing_scope_titles = [
            title for title in titles_by_unit_id.get(h_unit_id, [])
            if history_scope_key(h_unit_id, title) not in history_deep_refresh
        ]
        if not missing_scope_titles:
            continue
        direct_records = exclude_contract_changes(list(existing_history_by_unit.get(h_unit_id, {}).values()))
        needs_deep_scan = any(
            len([
                record for record in direct_records
                if is_recent_history(record) and is_comparable_history(title, record.get("title", ""))
            ]) < 2
            for title in missing_scope_titles
        )
        if not needs_deep_scan:
            continue
        if unit_total_pages[h_unit_id] <= 15:
            print(f"Scanning all {unit_total_pages[h_unit_id]} history pages for '{h_unit}'.")
            deep_history_items.extend(fetch_unit_history(
                h_unit_id,
                h_unit,
                comparable_titles=missing_scope_titles,
                start_page=2,
                scan_all_pages=True,
                deep_refresh_keys=[history_scope_key(h_unit_id, title) for title in missing_scope_titles]
            ))
        else:
            print(f"Using focused title history search for high-volume agency '{h_unit}'.")
            for title in missing_scope_titles:
                title_items, title_scan_completed = fetch_title_history(h_unit_id, h_unit, title)
                deep_history_items.extend(title_items)
                if title_scan_completed:
                    history_deep_refresh[history_scope_key(h_unit_id, title)] = refresh_date
    process_history_items(deep_history_items)

    unit_map = fetch_json_with_retry("https://pcc-api.openfun.app/api/unit", "procurement unit directory") or {}
    related_units_by_active_id = {}
    hierarchy_units_to_fetch = {}

    for h_unit, h_unit_id in active_units_dict.items():
        direct_records = list(existing_history_by_unit.get(h_unit_id, {}).values())
        needs_hierarchy = any(
            len([
                record for record in exclude_contract_changes(direct_records)
                if is_recent_history(record) and is_comparable_history(title, record.get("title", ""))
            ]) < 2
            for title in titles_by_unit_id.get(h_unit_id, [])
        )
        if not needs_hierarchy:
            continue
        related_units = get_related_units(h_unit_id, h_unit, unit_map)
        if not related_units:
            continue
        related_units_by_active_id[h_unit_id] = related_units
        for related_id, related_name in related_units.items():
            history_unit_names.setdefault(related_id, related_name)
            if (
                related_id not in queried_history_unit_ids
                and history_unit_refresh.get(related_id) != refresh_date
            ):
                hierarchy_units_to_fetch[related_id] = related_name

    if hierarchy_units_to_fetch:
        print(f"Direct history was insufficient; checking {len(hierarchy_units_to_fetch)} related units.")
        hierarchy_history_items = []
        all_active_titles = [
            item.get("brief", {}).get("title", "")
            for item in active_tenders
        ]
        def fetch_related_unit(unit_item):
            related_id, related_name = unit_item
            return fetch_unit_history(
                related_id,
                related_name,
                comparable_titles=all_active_titles,
                recent_only=True,
                request_delay=0.2
            )

        with ThreadPoolExecutor(max_workers=3) as executor:
            for related_items in executor.map(fetch_related_unit, hierarchy_units_to_fetch.items()):
                hierarchy_history_items.extend(related_items)
        process_history_items(hierarchy_history_items)

    for records in history_pool.values():
        records.sort(key=lambda record: record["award_date"], reverse=True)
    if failed_history_units:
        print(f"Deferred history refresh for {len(failed_history_units)} units; cached records were preserved.")
                        
    # Process, filter, and deduplicate active tenders
    seen_ids = set()
    seen_projects = set()
    processed_tenders = []
    previous_tenders_by_project = {
        (tender.get("unit_id", ""), tender.get("job_number", "")): tender
        for tender in existing_data.get("tenders", [])
    }
    
    for item in active_tenders:
        filename = item.get("filename", "")
        brief = item.get("brief", {})
        title = brief.get("title", "")
        brief_type = brief.get("type", "")
        unit_name = item.get("unit_name", "")
        date_raw = str(item.get("date", ""))
        unit_id = item.get("unit_id", "")
        job_number = item.get("job_number", "")
        project_key = (unit_id, job_number, date_raw, filename)
        tender_id = project_key
        
        if tender_id in seen_ids:
            continue
            
        detail_data = prefetched_details.get(project_key) or fetch_tender_detail_with_retry(unit_id, job_number)
        tender_url = ""
        real_budget = 0
        real_award = 0
        raw_winner = ""
        stage = ""
        relevance = item.get("relevance") or classify_tender_relevance(item)

        previous_tender = previous_tenders_by_project.get((unit_id, job_number))
        if detail_data is None and previous_tender:
            if get_title_scope_exclusion(previous_tender.get("title", "")):
                print(f"Excluded out-of-scope cached tender: {title}")
                continue
            processed_tenders.append(previous_tender)
            seen_ids.add(tender_id)
            seen_projects.add(project_key)
            print(f"Detail unavailable; preserved previous verified record: {title}")
            continue
        
        if detail_data and detail_data.get("records"):
            records = detail_data["records"]
            merged_detail = {}
            for record_index, record in enumerate(records):
                for key, value in record.get("detail", {}).items():
                    merged_detail[f"{record_index}:{key}"] = value
            detailed_relevance = classify_tender_relevance(item, merged_detail)
            if relevance.get("status") == "review":
                if detailed_relevance["status"] == "included":
                    relevance = detailed_relevance
                else:
                    continue
        elif relevance.get("status") == "review":
            review_candidates.append({
                "date": date_to_iso(date_raw), "title": title, "unit": unit_name,
                "unit_id": unit_id, "job_number": job_number,
                "tender_url": f"https://web.pcc.gov.tw/prkms/tender/common/noticeDate/redirectPublic?ds={date_raw}&fn={filename}.xml",
                "relevance": relevance
            })
            continue
            
            # Check if this tender has already been resolved/awarded or failed
            # Scan entire list to ensure successful awards take absolute precedence over historical failures
            award_record = None
            failed_record = None
            for r in records:
                r_type = r.get("brief", {}).get("type", "")
                if "無法決標" in r_type:
                    if not failed_record:
                        failed_record = r
                elif "決標" in r_type:
                    if not award_record:
                        award_record = r
            
            if award_record:
                failed_record = None
                
            if failed_record:
                # Bidding failed (流標/廢標)
                stage = "無法決標"
                detail_obj = failed_record.get("detail", {})
                tender_url = detail_obj.get("url", "")
                award_date_str = str(failed_record.get("date", ""))
                if award_date_str:
                    try:
                        # Check age (skip if older than 60 days)
                        award_date = datetime.strptime(award_date_str, "%Y%m%d")
                        taipei_now = datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=8))).replace(tzinfo=None)
                        delta = taipei_now - award_date
                        if delta.days > 60:
                            print(f"Skipping older failed tender: {title} (failed {delta.days} days ago)")
                            continue
                    except:
                        pass
                print(f"Failed tender found: {title} | Date: {award_date_str}")
            elif award_record:
                # Extract details from award notice
                detail_obj = award_record.get("detail", {})
                historical_winner = extract_winning_competitor(detail_obj)
                real_budget, real_award = extract_budget_and_award(detail_obj)
                
                # Check age of award notice (skip if older than 60 days to keep DB fresh)
                award_date_str = str(award_record.get("date", ""))
                if award_date_str:
                    try:
                        # Date format is typically YYYYMMDD
                        award_date = datetime.strptime(award_date_str, "%Y%m%d")
                        taipei_now = datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=8))).replace(tzinfo=None)
                        delta = taipei_now - award_date
                        if delta.days > 60:
                            # Skip old resolved tenders to keep DB active
                            print(f"Skipping older resolved tender: {title} (awarded {delta.days} days ago)")
                            continue
                    except:
                        pass
                
                # This is a recently resolved tender, keep it in DB as "已決標"
                stage = "已決標"
                raw_winner = historical_winner
                tender_url = detail_obj.get("url", "")
                print(f"Recently resolved tender found: {title} | Winner: {raw_winner} | Date: {award_date_str}")
            else:
                # Active tender
                # Get URL from the first record (newest active bulletin)
                first_record = records[0]
                detail_obj = first_record.get("detail", {})
                tender_url = detail_obj.get("url", "")
                if real_budget == 0:
                    real_budget, _ = extract_budget_and_award(detail_obj)
                
        if tender_url:
            if tender_url.startswith("http:"):
                tender_url = "https:" + tender_url[5:]
        else:
            tender_url = f"https://web.pcc.gov.tw/prkms/tender/common/noticeDate/redirectPublic?ds={date_raw}&fn={filename}.xml"
            
        seen_ids.add(tender_id)
        seen_projects.add(project_key)
        
        # Resolve stage
        if stage not in ["已決標", "無法決標"]:
            if "\u516c\u958b\u5fb5\u6c42" in brief_type:
                stage = "公開徵求價單"
                stage_color = "bg-amber-950/45 border-amber-500/40 text-amber-400"
            else:
                stage = "正式開標"
                stage_color = "bg-indigo-950/45 border-indigo-500/40 text-indigo-400"
        else:
            if stage == "已決標":
                stage_color = "bg-emerald-950/45 border-emerald-500/40 text-emerald-400"
            else:
                stage_color = "bg-rose-950/45 border-rose-500/40 text-rose-400"
            
        # Determine budget and discount stats
        final_budget_val = real_budget
        
        budget_str = f"NT$ {final_budget_val:,}" if final_budget_val > 0 else "無公開數據"
        
        duration = parse_contract_duration(title)

        candidate_unit_ids = list(related_units_by_active_id.get(unit_id, {unit_id: unit_name}))
        candidate_history_records = []
        for source_unit_id in candidate_unit_ids:
            for record in existing_history_by_unit.get(source_unit_id, {}).values():
                if record.get("job_number") == job_number or not is_comparable_history(title, record.get("title", "")):
                    continue
                candidate_history_records.append({
                    **record,
                    "source_unit_id": source_unit_id,
                    "source_unit": history_unit_names.get(source_unit_id, unit_name),
                    "relation_scope": "same_unit" if source_unit_id == unit_id else "same_parent_org"
                })
        history_records = exclude_contract_changes(candidate_history_records)
        for record in history_records:
            record["is_stale"] = not is_recent_history(record)
        history_records.sort(key=lambda record: record.get("award_date", ""), reverse=True)
        history_records.sort(key=lambda record: record["is_stale"])
        recent_history_records = [record for record in history_records if not record["is_stale"]]
        usable_rates = [
            record["discount_rate"] for record in recent_history_records
            if record["discount_rate"] is not None and 50 <= record["discount_rate"] <= 100
        ]
        historical_median = median(usable_rates) if len(usable_rates) >= 2 else None
        avg_discount_str = f"{historical_median:.1f}%" if historical_median is not None else "資料不足"
        if len(usable_rates) >= 2:
            discount_source = f"近 5 年 {len(usable_rates)} 筆同設備、同契約型態決標折扣中位數"
        elif usable_rates:
            discount_source = "近 5 年僅 1 筆有效可比資料；至少需 2 筆才推估"
        else:
            discount_source = "近 5 年查無同設備、同契約型態且具完整金額的決標"
        if final_budget_val > 0 and historical_median is not None:
            suggested_price_val = int(final_budget_val * historical_median / 100)
            suggested_price_val = (suggested_price_val // 1000) * 1000
            suggested_price_str = f"NT$ {suggested_price_val:,}"
        else:
            suggested_price_str = "資料不足"

        history_stats = [
            {
                "year": record["year"],
                "val": int(record["discount_rate"]) if record["discount_rate"] is not None else 0,
                "type": "real",
                "winner": record["winner"]
            }
            for record in reversed(recent_history_records)
            if record["discount_rate"] is not None and 50 <= record["discount_rate"] <= 100
        ]

        if raw_winner:
            main_competitor = map_competitor_name(raw_winner)
        else:
            main_competitor = next(
                (record["winner"] for record in recent_history_records if record["winner"] != "未公開"),
                "無公開數據"
            )
            
        # Extract real publication date and bidding deadline from detail records
        publish_date_str = ""
        deadline_str = ""
        if detail_data and detail_data.get("records"):
            for r in detail_data["records"]:
                r_detail = r.get("detail", {})
                if r_detail:
                    p_date, d_date = extract_dates(r_detail, date_raw)
                    if p_date:
                        publish_date_str = p_date
                    if d_date:
                        deadline_str = d_date
                    if publish_date_str and deadline_str:
                        break
                        
        if not publish_date_str:
            if len(date_raw) == 8:
                try:
                    publish_date_str = datetime.strptime(date_raw, "%Y%m%d").strftime("%Y-%m-%d")
                except:
                    pass
        if not deadline_str and publish_date_str:
            try:
                deadline_str = (datetime.strptime(publish_date_str, "%Y-%m-%d") + timedelta(days=14)).strftime("%Y-%m-%d")
            except:
                pass
        if not deadline_str:
            deadline_str = "未公開"
            
        city = get_city(unit_name)
        tag = "重點攻堅" if final_budget_val >= 2500000 else "一般監控"
        tag_color = "bg-red-950/45 border-red-500/40 text-red-400" if tag == "重點攻堅" else "bg-slate-900 border-slate-700 text-slate-400"
        
        award_price_str = ""
        if real_award > 0:
            if real_award < 2000 or (real_budget > 0 and (real_award / real_budget) < 0.02):
                award_price_str = f"NT$ {real_award:,} (單價決標)"
            else:
                award_price_str = f"NT$ {real_award:,}"

        processed_tenders.append({
            "city": city,
            "tag": tag,
            "tag_color": tag_color,
            "title": title,
            "unit": unit_name,
            "unit_id": unit_id,
            "job_number": job_number,
            "publish_date": publish_date_str,
            "deadline": deadline_str,
            "budget": budget_str,
            "award_price": award_price_str,
            "avg_discount": avg_discount_str,
            "discount_source": discount_source,
            "main_competitor": main_competitor,
            "suggested_price": suggested_price_str,
            "suggestion_basis": {
                "method": "近5年同設備與同契約型態歷史決標折扣中位數（至少2筆）",
                "record_count": len(usable_rates),
                "discount_rate": round(historical_median, 1) if historical_median is not None else None
            },
            "tender_url": tender_url,
            "history_stats": history_stats,
            "history_records": history_records,
            "stage": stage,
            "stage_color": stage_color,
            "duration_years": duration,
            "relevance": relevance
        })
        
        print(f"Processed: {title} | Date: {date_raw} | Winner: {main_competitor} | Budget: {budget_str}")
        
        time.sleep(1.2)
        
    # Keep still-recent records from the previous successful run while the
    # date-based backfill is being completed incrementally.
    current_project_keys = {
        (tender.get("unit_id", ""), tender.get("job_number", ""))
        for tender in processed_tenders
    }
    reviewed_project_keys = {
        (candidate.get("unit_id", ""), candidate.get("job_number", ""))
        for candidate in review_candidates
    }
    cutoff_iso = (today - timedelta(days=60)).strftime("%Y-%m-%d")
    for previous in existing_data.get("tenders", []):
        previous_key = (previous.get("unit_id", ""), previous.get("job_number", ""))
        if (
            previous_key in current_project_keys
            or previous_key in reviewed_project_keys
            or previous.get("publish_date", "") < cutoff_iso
            or get_title_scope_exclusion(previous.get("title", ""))
        ):
            continue
        processed_tenders.append(previous)
        current_project_keys.add(previous_key)
    processed_tenders.sort(key=lambda tender: tender.get("publish_date", ""), reverse=True)

    candidate_by_id = {}
    for candidate in raw_active_tenders:
        candidate_id = (
            candidate.get("unit_id", ""), candidate.get("job_number", ""),
            str(candidate.get("date", "")), candidate.get("filename", "")
        )
        candidate_by_id[candidate_id] = candidate
    candidate_cache = sorted(
        candidate_by_id.values(), key=lambda candidate: str(candidate.get("date", "")), reverse=True
    )

    backfill_remaining = sum(
        1 for days_ago in range(2, 61)
        if collection_days.get((today - timedelta(days=days_ago)).strftime("%Y-%m-%d"), {}).get("status") != "complete"
    )
    today_summary = collection_days.get(today.strftime("%Y-%m-%d"), {})

    # Force last_updated to be in Taipei Time (UTC+8) regardless of runner timezone
    taipei_time = datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=8)))
    last_updated_str = taipei_time.strftime("%Y-%m-%d %H:%M")

    previous_collection_status = dict(existing_data.get("collection_status", {}))
    collection_status = {
        **previous_collection_status,
        "today": today.strftime("%Y-%m-%d"),
        "status": today_summary.get("status", previous_collection_status.get("status", "incomplete")),
        "source_records": today_summary.get("source_records", previous_collection_status.get("source_records", 0)),
        "candidate_records": today_summary.get("candidate_records", previous_collection_status.get("candidate_records", 0)),
        "review_records": len(review_candidates),
        "backfill_remaining_days": backfill_remaining,
        "source": "政府電子採購網每日公告資料"
    }
    if mode == "live":
        collection_status.update({
            "latest_attempt_status": "complete" if not failed_dates else "partial",
            "latest_attempt_at": last_updated_str,
            "successful_dates": successful_dates,
            "failed_dates": failed_dates
        })
    else:
        collection_status["maintenance"] = {
            "status": "complete" if not failed_dates else "partial",
            "last_run_at": last_updated_str,
            "backfill_dates": successful_dates,
            "failed_dates": failed_dates
        }
    
    output_data = {
        "last_updated": last_updated_str,
        "tenders": processed_tenders,
        "collection_status": collection_status,
        "collection_days": collection_days,
        "candidate_cache": candidate_cache,
        "review_candidates": review_candidates,
        "history_cache": sorted(
            [
                {
                    "unit_id": unit_id,
                    "unit_name": history_unit_names.get(unit_id, ""),
                    **record
                }
                for unit_id, records in existing_history_by_unit.items()
                for record in records.values()
            ],
            key=lambda record: record.get("award_date", ""),
            reverse=True
        ),
        "history_unit_refresh": history_unit_refresh,
        "history_deep_refresh": history_deep_refresh
    }
    
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)
        
    print(f"Successfully updated database. Saved {len(processed_tenders)} tenders to {output_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Update tender intelligence data.")
    parser.add_argument("--mode", choices=("live", "maintenance"), default="live")
    arguments = parser.parse_args()
    main(arguments.mode)
