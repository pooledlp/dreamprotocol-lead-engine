from __future__ import annotations

from typing import Dict, List, Set
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from .extractors import extract_contacts, filter_emails
from .utils import DATA_DIR, normalize_domain, read_csv, write_csv

KEYWORDS = ["contact", "about", "team", "staff", "service", "services", "book", "booking", "appointment", "schedule", "quote", "estimate", "patient", "location"]
COMMON_PATHS = ["/", "/contact", "/contact-us", "/about", "/about-us", "/team", "/staff", "/services", "/book", "/booking", "/appointment", "/appointments", "/schedule", "/request-quote", "/free-estimate", "/new-patient", "/locations"]


def detect_platform(html: str) -> str:
    low = html.lower()
    for p in ["wordpress", "wix", "squarespace", "webflow", "shopify"]:
        if p in low:
            return p
    return ""


def crawl_site(url: str, max_pages: int = 10) -> Dict[str, str]:
    domain = normalize_domain(url)
    to_visit = [url]
    for path in COMMON_PATHS:
        to_visit.append(urljoin(url, path))
    visited: Set[str] = set()
    emails: List[str] = []
    phones: List[str] = []
    contact_page = booking_page = quote_page = ""
    contact_form = chatbot = booking = False
    platform = ""

    while to_visit and len(visited) < max_pages:
        page = to_visit.pop(0)
        if page in visited:
            continue
        visited.add(page)
        try:
            r = requests.get(page, timeout=20)
            if r.status_code >= 400:
                continue
            html = r.text
        except Exception:
            continue
        platform = platform or detect_platform(html)
        extracted = extract_contacts(html)
        emails.extend(extracted["emails"])
        phones.extend(extracted["phones"])

        soup = BeautifulSoup(html, "html.parser")
        if soup.select("form"):
            contact_form = True
        if "chat" in html.lower() or "intercom" in html.lower() or "drift" in html.lower():
            chatbot = True
        if "book" in html.lower() or "appointment" in html.lower() or "schedule" in html.lower():
            booking = True

        for a in soup.select("a[href]"):
            href = urljoin(page, a.get("href", ""))
            if normalize_domain(href) != domain:
                continue
            text = (a.get_text(" ", strip=True) + " " + href).lower()
            if any(k in text for k in KEYWORDS) and href not in visited and href not in to_visit:
                to_visit.append(href)
            if "contact" in text and not contact_page:
                contact_page = href
            if any(k in text for k in ["book", "booking", "appointment", "schedule"]) and not booking_page:
                booking_page = href
            if any(k in text for k in ["quote", "estimate"]) and not quote_page:
                quote_page = href

    email_result = filter_emails(emails, domain)
    return {
        "website": url,
        "domain": domain,
        "emails": ";".join(email_result["good"]),
        "junk_emails": ";".join(email_result["junk"]),
        "phones": ";".join(sorted(set(phones))),
        "contact_page_url": contact_page,
        "booking_page_url": booking_page,
        "quote_page_url": quote_page,
        "contact_form_present": str(contact_form),
        "chatbot_present": str(chatbot),
        "online_booking_present": str(booking),
        "platform": platform,
    }


def crawl_discovered_websites() -> List[Dict[str, str]]:
    seeds = read_csv(DATA_DIR / "marin_discovered_websites.csv")
    out = []
    for s in seeds:
        site = s.get("website", "")
        if not site:
            continue
        row = {**s, **crawl_site(site)}
        out.append(row)
    write_csv(DATA_DIR / "marin_crawled_websites.csv", out)
    return out
