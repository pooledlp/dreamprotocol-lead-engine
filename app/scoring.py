from typing import Dict

HIGH_VALUE = {"dentist", "dental office", "med spa", "law firm", "property management", "hvac", "roofer", "contractor"}
APPT_HEAVY = {"dentist", "dental office", "med spa", "chiropractor", "veterinary clinic", "salon", "spa", "fitness gym"}
QUOTE_HEAVY = {"hvac", "plumber", "electrician", "roofer", "contractor"}
PHONE_HEAVY = {"restaurant", "hotel", "catering", "plumber", "electrician", "hvac", "property management"}
DISPATCH_HEAVY = {"hvac", "plumber", "electrician", "roofer", "property management", "contractor"}
MEDICAL = {"dentist", "dental office", "med spa", "chiropractor"}
CONTRACTORS = {"hvac", "plumber", "electrician", "roofer", "contractor"}


def _truthy(row: Dict[str, str], key: str) -> bool:
    return row.get(key) == "True"


def detect_business_type(row: Dict[str, str]) -> str:
    category = row.get("category", "").lower()
    text = f"{category} {row.get('business_name', '')} {row.get('website', '')}".lower()
    if "property management" in text:
        return "property_management"
    if any(term in text for term in ["hvac", "plumber", "electrician", "roofer", "contractor"]):
        return "contractor_home_services"
    if any(term in text for term in ["dentist", "dental", "med spa", "chiropractor"]):
        return "appointment_health_wellness"
    if any(term in text for term in ["restaurant", "catering", "hotel"]):
        return "hospitality_phone_heavy"
    return category.replace(" ", "_") or "local_service"


def pain_angle_for(row: Dict[str, str]) -> str:
    business_type = row.get("business_type") or detect_business_type(row)
    if business_type == "contractor_home_services":
        return "missed emergency calls, quote intake, dispatch coordination, and after-hours lead capture"
    if business_type == "appointment_health_wellness":
        return "appointment booking, no-show reduction, and intake automation"
    if business_type == "property_management":
        return "maintenance intake, tenant coordination, and showing scheduling"
    return "manual lead handling, missed calls, and slow inbound follow-up"


def score_lead(row: Dict[str, str]) -> Dict[str, str]:
    score = 0
    category = row.get("category", "").lower()
    city = row.get("city", "")
    platform = row.get("platform", "")
    phone_count = int(row.get("phone_count") or (len([p for p in row.get("phones", "").split(";") if p])) or 0)

    business_type = detect_business_type(row)
    likely_quote_driven = category in QUOTE_HEAVY or _truthy(row, "quote_language_present") or bool(row.get("quote_page_url"))
    likely_dispatch_driven = category in DISPATCH_HEAVY
    likely_after_hours = category in DISPATCH_HEAVY or _truthy(row, "emergency_language_present")
    likely_missed_call = category in PHONE_HEAVY or phone_count >= 2 or likely_after_hours

    if row.get("emails"):
        score += 20
    if row.get("phones"):
        score += 10
    if row.get("contact_page_url"):
        score += 10
    if _truthy(row, "contact_form_present"):
        score += 10
    if row.get("chatbot_present") != "True":
        score += 15
    if row.get("online_booking_present") != "True":
        score += 15
    if platform in {"WordPress", "Wix"}:
        score += 15
    if category in HIGH_VALUE:
        score += 20
    if category in APPT_HEAVY:
        score += 10
    if likely_quote_driven:
        score += 15
    if likely_after_hours:
        score += 10
    if likely_missed_call:
        score += 15
    if city:
        score += 10

    priority = "Hot" if score >= 90 else "Warm" if score >= 65 else "Low"

    row["business_type"] = business_type
    row["likely_after_hours_opportunity"] = str(likely_after_hours)
    row["likely_missed_call_risk"] = str(likely_missed_call)
    row["likely_quote_driven"] = str(likely_quote_driven)
    row["likely_dispatch_driven"] = str(likely_dispatch_driven)
    row["lead_score"] = str(score)
    row["priority"] = priority
    row["pain_angle"] = pain_angle_for(row)
    row["recommended_offer"] = "AI receptionist + instant intake workflow tailored to the site's highest-friction lead path"
    row["personalized_first_line"] = f"Noticed {row.get('business_name', 'your business')} serves {city}; your website suggests a few fast wins around {row['pain_angle']}."
    return row
