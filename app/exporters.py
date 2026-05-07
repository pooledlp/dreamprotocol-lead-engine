from typing import Dict, List

from .scoring import CONTRACTORS, MEDICAL, score_lead
from .utils import DATA_DIR, dedupe_records, read_csv, write_csv


def _write_logged(name: str, rows: List[Dict[str, str]]) -> None:
    path = DATA_DIR / name
    write_csv(path, rows)
    print(f"[EXPORT] Wrote {path} rows={len(rows)}", flush=True)


def _category(row: Dict[str, str]) -> str:
    return row.get("category", "").lower()


def export_all() -> List[Dict[str, str]]:
    rows = read_csv(DATA_DIR / "bayarea_crawled_websites.csv") or read_csv(DATA_DIR / "marin_crawled_websites.csv")
    scored = dedupe_records([score_lead(r) for r in rows])

    _write_logged("bayarea_all_leads.csv", scored)
    _write_logged("bayarea_hot_leads.csv", [r for r in scored if int(r.get("lead_score", 0)) >= 90 or r.get("priority") == "Hot"])
    _write_logged("bayarea_phone_heavy.csv", [r for r in scored if r.get("likely_missed_call_risk") == "True" or r.get("primary_phone")])
    _write_logged("bayarea_medical.csv", [r for r in scored if _category(r) in MEDICAL or r.get("business_type") == "appointment_health_wellness"])
    _write_logged("bayarea_contractors.csv", [r for r in scored if _category(r) in CONTRACTORS or r.get("business_type") == "contractor_home_services"])
    _write_logged("bayarea_property_management.csv", [r for r in scored if r.get("business_type") == "property_management"])

    # Backward-compatible Marin exports for older automations.
    _write_logged("marin_all_leads.csv", scored)
    _write_logged("marin_email_leads.csv", [r for r in scored if r.get("emails")])
    _write_logged("marin_high_score_leads.csv", [r for r in scored if int(r.get("lead_score", 0)) >= 90])
    _write_logged("marin_no_email_contact_form_leads.csv", [r for r in scored if not r.get("emails") and r.get("contact_form_present") == "True"])

    junk_rows = []
    for r in scored:
        for e in filter(None, r.get("junk_emails", "").split(";")):
            junk_rows.append({"website": r.get("website", ""), "business_name": r.get("business_name", ""), "junk_email": e})
    _write_logged("marin_junk_filtered_emails.csv", junk_rows)
    return scored
