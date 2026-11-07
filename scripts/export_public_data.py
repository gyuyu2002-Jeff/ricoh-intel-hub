"""Export only public procurement facts; private state must never be published."""

import argparse
import json
from pathlib import Path
from urllib.parse import urlsplit


TENDER_FIELDS = (
    "city", "city_source", "city_confidence", "title", "unit", "unit_id",
    "job_number", "publish_date", "publish_date_confidence", "deadline",
    "deadline_confidence", "award_date", "budget", "award_price", "stage",
    "stream", "sub_type", "tender_url",
)
HISTORY_FIELDS = (
    "award_date", "year", "title", "job_number", "budget", "award_price",
    "discount_rate", "winner", "source_url", "official_verified",
    "verification_source", "relation_scope", "source_unit", "source_unit_id",
    "is_stale",
)
FORECAST_FIELDS = (
    "id", "unit_id", "unit", "city", "series_title", "predicted_title",
    "latest_title", "latest_job_number", "latest_source_url", "latest_award_date",
    "latest_award_price", "latest_award_price_str", "latest_winner",
    "predicted_date", "predicted_month", "predicted_range", "predicted_range_start",
    "predicted_range_end", "prediction_as_of", "cadence_months", "cadence_summary", "history_count",
)
STATUS_FIELDS = ("today", "status", "latest_attempt_status", "latest_attempt_at", "source")
CURRENT_STATUS_FIELDS = ("status", "date", "job_number", "notice_url", "stage", "title")
RELEVANCE_FIELDS = ("status", "category", "confidence", "stream", "sub_type")


def public_fields(record, fields):
    result = {}
    for key in fields:
        value = record.get(key)
        if value is None or not isinstance(value, (str, int, float, bool)):
            continue
        if key.endswith("url"):
            parsed = urlsplit(str(value))
            if parsed.scheme != "https" or parsed.hostname not in {"web.pcc.gov.tw", "pcc.gov.tw"} or parsed.username:
                continue
        if "winner" in key and isinstance(value, str):
            value = value.replace("本公司 (互盛 RICOH)", "互盛（RICOH）").replace("本公司", "互盛")
        result[key] = value
    return result


def records(value):
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def public_tender(record):
    result = public_fields(record, TENDER_FIELDS)
    if record.get("stage") == "已決標":
        winner = record.get("winner") or record.get("main_competitor")
        result.update(public_fields({"winner": winner}, ("winner",)))
    result["history_records"] = [public_fields(item, HISTORY_FIELDS) for item in records(record.get("history_records"))]
    result["relevance"] = public_fields(record.get("relevance") or {}, RELEVANCE_FIELDS)
    return result


def public_forecast(record):
    result = public_fields(record, FORECAST_FIELDS)
    result["history_track"] = [
        public_fields(item, HISTORY_FIELDS + ("date", "month", "index"))
        for item in records(record.get("history_track"))
    ]
    result["current_status"] = public_fields(record.get("current_status") or {}, CURRENT_STATUS_FIELDS)
    result["prediction_basis"] = public_fields(record.get("prediction_basis") or {}, (
        "method", "source_count", "lead_time_days", "contract_end_verified",
    ))
    return result


def export_public_data(source):
    if not isinstance(source, dict) or not isinstance(source.get("tenders"), list):
        raise ValueError("Expected a dataset object with a tenders array")
    result = public_fields(source, ("last_updated",))
    result["tenders"] = [public_tender(item) for item in records(source["tenders"])]
    result["review_candidates"] = [public_tender(item) for item in records(source.get("review_candidates"))]
    result["forecasted_tenders"] = [public_forecast(item) for item in records(source.get("forecasted_tenders"))]
    status = source.get("collection_status") or {}
    result["collection_status"] = public_fields(status, STATUS_FIELDS)
    for key in ("successful_dates", "failed_dates"):
        result["collection_status"][key] = [value for value in status.get(key, []) if isinstance(value, str)]
    result["collection_status"]["maintenance"] = public_fields(status.get("maintenance") or {}, ("status", "last_run_at"))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True)
    parser.add_argument("--output", action="append", default=[])
    parser.add_argument("--check", action="store_true", help="Fail if source contains non-public fields")
    args = parser.parse_args()
    source = json.loads(Path(args.source).read_text(encoding="utf-8"))
    exported = export_public_data(source)
    if args.check and exported != source:
        raise SystemExit("Dataset contains fields outside the public schema")
    if not args.check and not args.output:
        parser.error("provide --output or --check")
    for target in args.output:
        Path(target).write_text(json.dumps(exported, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Public dataset schema verified" if args.check else "Public dataset exported")


if __name__ == "__main__":
    main()
