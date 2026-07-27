# -*- coding: utf-8 -*-
import urllib.request
import urllib.parse
import json
import re
import html
import ssl
from datetime import datetime, timezone, timedelta
import os
import time

OFFICIAL_AWARD_SEARCH_URL = "https://web.pcc.gov.tw/prkms/tender/common/agent/readTenderAgent"
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
    for k, v in detail.items():
        if "得標廠商" in k and not any(x in k for x in ["國家", "金額", "地址", "電話", "統編", "序號"]) and v:
            val = str(v).strip()
            if val and len(val) > 2 and "中華民國" not in val:
                winner = val
                break
                
    if not winner:
        companies = {}
        for k, v in detail.items():
            match_name = re.match(r'投標廠商:投標廠商(\d+):廠商名稱', k)
            if match_name:
                idx = match_name.group(1)
                companies[idx] = str(v).strip()
                
        for k, v in detail.items():
            match_won = re.match(r'投標廠商:投標廠商(\d+):是否得標', k)
            if match_won and str(v).strip() in ["是", "得標"]:
                idx = match_won.group(1)
                if idx in companies:
                    winner = companies[idx]
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
    normalized = title.replace("臺", "台")
    excluded = ["耗材", "碳粉", "墨水", "色帶", "零件", "影印裝訂", "藍晒", "車銑", "鑽銑", "CNC", "機械科"]
    equipment = ["影印機", "複合機", "事務機", "多功能機", "印表機", "複印機"]
    return not any(word in normalized for word in excluded) and any(word in normalized for word in equipment)

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
    req_detail = urllib.request.Request(detail_api_url, headers={'User-Agent': 'Mozilla/5.0'})
    
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
    request = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    for attempt in range(max_retries):
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.loads(response.read().decode('utf-8'))
        except urllib.error.HTTPError as error:
            if error.code != 429 or attempt + 1 == max_retries:
                print(f"{label} failed: {error}")
                return None
            wait_time = (attempt + 1) * 5
            print(f"{label} rate limited. Retrying in {wait_time} seconds...")
            time.sleep(wait_time)
        except Exception as error:
            print(f"{label} failed: {error}")
            return None
    return None

def main():
    print("Starting automated tender data updater with real stats...")
    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_path = os.path.join(script_dir, "data.json")
    existing_history_by_unit = {}
    history_unit_names = {}

    try:
        with open(output_path, "r", encoding="utf-8") as existing_file:
            existing_data = json.load(existing_file)

        cached_records = list(existing_data.get("history_cache", []))
        for tender in existing_data.get("tenders", []):
            unit_id = tender.get("unit_id", "")
            unit_name = tender.get("unit", "")
            for record in tender.get("history_records", []):
                cached_records.append({"unit_id": unit_id, "unit_name": unit_name, **record})

        for cached in cached_records:
            unit_id = cached.get("unit_id", "")
            unit_name = cached.get("unit_name", "")
            job_number = cached.get("job_number", "")
            if not unit_id or not job_number or cached.get("official_verified") is not True:
                continue
            history_unit_names[unit_id] = unit_name
            history_record = {
                key: value for key, value in cached.items()
                if key not in ("unit_id", "unit_name")
            }
            existing_history_by_unit.setdefault(unit_id, {})[job_number] = history_record
        print(f"Loaded {sum(len(records) for records in existing_history_by_unit.values())} verified cached histories.")
    except (FileNotFoundError, json.JSONDecodeError) as error:
        print(f"No usable history cache found: {error}")

    keywords = ["影印機", "複合機", "事務機", "印表機", "複印機"]
    raw_active_tenders = []
    
    for kw in keywords:
        encoded_kw = urllib.parse.quote(kw)
        url = f"https://pcc-api.openfun.app/api/searchbytitle?query={encoded_kw}"
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req) as response:
                content = response.read().decode('utf-8')
                data = json.loads(content)
                if isinstance(data, dict) and "records" in data:
                    raw_active_tenders.extend(data["records"])
                    print(f"Fetched {len(data['records'])} items for active search '{kw}'")
        except Exception as e:
            print(f"Error fetching active data for '{kw}': {e}")
            
    if not raw_active_tenders:
        print("No tender data received from API. Aborting update.")
        return
        
    # Filter and identify active tenders and their units
    active_tenders = []
    seen_active_projects = set()
    active_units_dict = {}
    
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
        title = brief.get("title", "")
        brief_type = brief.get("type", "")
        unit_name = item.get("unit_name", "")
        date_raw = str(item.get("date", ""))
        unit_id = item.get("unit_id", "")
        
        # 1. STRICT ACTIVE FILTER: Exclude resolved/failed from active list
        if "\u6c7a\u6a19" in brief_type or "\u7121\u6cd5\u6c7a\u6a19" in brief_type:
            continue
            
        # 2. STRICT TIMELINESS FILTER: 2026 onwards
        if int(date_raw) < 20260101:
            continue
            
        # 3. Skip Bank of Taiwan central procurement
        if "\u81fa\u7063\u9280\u884c" in unit_name or "\u53f0\u7063\u9280\u884c" in unit_name:
            continue
            
        # 4. Skip consumables, toners, inks, ribbons, and parts
        title_norm = title.replace("\u81fa", "\u53f0")
        skip_kws = ["\u8017\u6750", "\u78b3\u7c89", "\u58a8\u6c34", "\u8272\u5e36", "\u96f6\u4ef6"]
        if any(sk in title_norm for sk in skip_kws):
            continue
            
        # 5. Skip duplicates
        project_key = (unit_name, title)
        if project_key in seen_active_projects:
            continue
            
        # 6. Keep office equipment; exclude machine-tool titles such as 車銑複合機.
        if not is_relevant_equipment_title(title_norm):
            continue
            
        seen_active_projects.add(project_key)
        active_tenders.append(item)
        active_units_dict[unit_name] = unit_id
        
    print(f"Identified {len(active_tenders)} active/recent tenders from {len(active_units_dict)} units.")
    
    # Fetch every successful equipment award returned for each monitored agency.
    # Keep one record per procurement job instead of collapsing records by year.
    raw_history_tenders = []
    failed_history_units = []
    print("Querying complete award history for all active agencies...")
    for h_unit, h_unit_id in active_units_dict.items():
        if not h_unit_id:
            continue
        url_unit = f"https://pcc-api.openfun.app/api/listbyunit?unit_id={h_unit_id}"
        data_unit = fetch_json_with_retry(url_unit, f"listbyunit for '{h_unit}' ({h_unit_id})")
        if data_unit is None:
            failed_history_units.append(h_unit)
            print(f"Keeping cached award history for '{h_unit}' and continuing.")
            continue
        for record in data_unit.get("records", []):
            if not isinstance(record, dict):
                continue
            brief = record.get("brief", {})
            notice_type = brief.get("type", "")
            if "決標" not in notice_type or "無法決標" in notice_type:
                continue
            if not is_relevant_equipment_title(brief.get("title", "")):
                continue
            record["unit_name"] = h_unit
            raw_history_tenders.append(record)
        time.sleep(1)

    history_pool = {
        unit: list(existing_history_by_unit.get(unit_id, {}).values())
        for unit, unit_id in active_units_dict.items()
    }
    seen_history_jobs = set()
    for h_item in sorted(raw_history_tenders, key=lambda item: int(item.get("date", 0)), reverse=True):
        h_unit = h_item.get("unit_name", "")
        h_unit_id = h_item.get("unit_id", "")
        h_job = h_item.get("job_number", "")
        job_key = (h_unit_id, h_job)
        if not h_unit_id or not h_job or job_key in seen_history_jobs:
            continue
        seen_history_jobs.add(job_key)

        if h_job in existing_history_by_unit.get(h_unit_id, {}):
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
        history_pool[h_unit].append(history_record)
        existing_history_by_unit.setdefault(h_unit_id, {})[h_job] = history_record
        history_unit_names[h_unit_id] = h_unit
        print(f"Saved verified history: {h_unit} | {h_date} | {h_job} | Budget {h_budget} | Award {h_award}")

    for records in history_pool.values():
        records.sort(key=lambda record: record["award_date"], reverse=True)
    if failed_history_units:
        print(f"Deferred history refresh for {len(failed_history_units)} units; cached records were preserved.")
                        
    # Process, filter, and deduplicate active tenders
    seen_ids = set()
    seen_projects = set()
    processed_tenders = []
    
    for item in active_tenders:
        filename = item.get("filename", "")
        brief = item.get("brief", {})
        title = brief.get("title", "")
        brief_type = brief.get("type", "")
        unit_name = item.get("unit_name", "")
        date_raw = str(item.get("date", ""))
        unit_id = item.get("unit_id", "")
        job_number = item.get("job_number", "")
        project_key = (unit_name, title)
        
        digits = re.findall(r'\d+', filename)
        if not digits:
            continue
        tender_id = digits[-1]
        
        if tender_id in seen_ids:
            continue
            
        detail_data = fetch_tender_detail_with_retry(unit_id, job_number)
        tender_url = ""
        real_budget = 0
        real_award = 0
        raw_winner = ""
        stage = ""
        
        if detail_data and detail_data.get("records"):
            records = detail_data["records"]
            
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

        history_records = [
            record for record in history_pool.get(unit_name, [])
            if record["job_number"] != job_number
        ]
        usable_rates = [
            record["discount_rate"] for record in history_records
            if record["discount_rate"] is not None and 50 <= record["discount_rate"] <= 100
        ]
        historical_median = median(usable_rates) if usable_rates else None
        avg_discount_str = f"{historical_median:.1f}%" if historical_median is not None else "資料不足"
        discount_source = (
            f"政府電子採購網 {len(usable_rates)} 筆有效歷史決標折扣中位數"
            if usable_rates else "查無可比較的歷史預算與決標價"
        )
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
            for record in reversed(history_records)
        ]

        if raw_winner:
            main_competitor = map_competitor_name(raw_winner)
        else:
            main_competitor = next(
                (record["winner"] for record in history_records if record["winner"] != "未公開"),
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
                "method": "歷史決標折扣中位數",
                "record_count": len(usable_rates),
                "discount_rate": round(historical_median, 1) if historical_median is not None else None
            },
            "tender_url": tender_url,
            "history_stats": history_stats,
            "history_records": history_records,
            "stage": stage,
            "stage_color": stage_color,
            "duration_years": duration
        })
        
        print(f"Processed: {title} | Date: {date_raw} | Winner: {main_competitor} | Budget: {budget_str}")
        
        time.sleep(1.2)
        
        if len(processed_tenders) >= 15:
            break
            
    # Force last_updated to be in Taipei Time (UTC+8) regardless of runner timezone
    taipei_time = datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=8)))
    last_updated_str = taipei_time.strftime("%Y-%m-%d %H:%M")
    
    output_data = {
        "last_updated": last_updated_str,
        "tenders": processed_tenders,
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
        )
    }
    
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)
        
    print(f"Successfully updated database. Saved {len(processed_tenders)} tenders to {output_path}")

if __name__ == "__main__":
    main()
