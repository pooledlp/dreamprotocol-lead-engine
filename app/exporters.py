from typing import Dict, List

from .scoring import score_lead
from .utils import DATA_DIR, read_csv, write_csv


def export_all() -> List[Dict[str, str]]:
    rows = read_csv(DATA_DIR / "marin_crawled_websites.csv")
    scored = [score_lead(r) for r in rows]

    write_csv(DATA_DIR / "marin_all_leads.csv", scored)
    write_csv(DATA_DIR / "marin_email_leads.csv", [r for r in scored if r.get("emails")])
    write_csv(DATA_DIR / "marin_high_score_leads.csv", [r for r in scored if int(r.get("lead_score", 0)) >= 80])
    write_csv(DATA_DIR / "marin_no_email_contact_form_leads.csv", [r for r in scored if not r.get("emails") and r.get("contact_form_present") == "True"])

    junk_rows = []
    for r in scored:
        for e in filter(None, r.get("junk_emails", "").split(";")):
            junk_rows.append({"website": r.get("website", ""), "business_name": r.get("business_name", ""), "junk_email": e})
    write_csv(DATA_DIR / "marin_junk_filtered_emails.csv", junk_rows)
    return scored
