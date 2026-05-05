from typing import Dict

HIGH_VALUE = {"dentist", "med spa", "law firm", "property management", "hvac", "roofer", "contractor"}
APPT_HEAVY = {"dentist", "dental office", "med spa", "chiropractor", "veterinary clinic", "salon", "spa", "fitness gym"}
QUOTE_HEAVY = {"hvac", "plumber", "electrician", "roofer", "contractor"}
PHONE_HEAVY = {"restaurant", "hotel", "catering", "plumber", "electrician"}


def score_lead(row: Dict[str, str]) -> Dict[str, str]:
    score = 0
    category = row.get("category", "").lower()
    city = row.get("city", "")

    if row.get("emails"):
        score += 20
    if row.get("phones"):
        score += 10
    if row.get("contact_page_url"):
        score += 10
    if row.get("contact_form_present") == "True":
        score += 10
    if row.get("chatbot_present") != "True":
        score += 10
    if row.get("online_booking_present") != "True":
        score += 10
    if category in HIGH_VALUE:
        score += 20
    if category in APPT_HEAVY:
        score += 10
    if category in QUOTE_HEAVY:
        score += 10
    if category in PHONE_HEAVY:
        score += 10
    if city:
        score += 10

    priority = "Hot" if score >= 80 else "Warm" if score >= 60 else "Low"

    row["lead_score"] = str(score)
    row["priority"] = priority
    row["pain_angle"] = "Manual lead handling and missed inbound opportunities"
    row["recommended_offer"] = "AI-powered website inquiry triage + instant response workflow"
    row["personalized_first_line"] = f"Noticed {row.get('business_name', 'your business')} serves {city}; I found a few automation quick wins on your website."
    return row
