from __future__ import annotations

import os
import time
from typing import Dict, List, Set
from urllib.parse import urldefrag, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from .extractors import extract_contacts, filter_emails
from .utils import DATA_DIR, ensure_http_url, normalize_domain, read_csv, registrable_domain, write_csv

KEYWORDS = [
    "contact", "about", "team", "staff", "service", "services", "book", "booking", "appointment",
    "schedule", "quote", "estimate", "patient", "location",
]
COMMON_PATHS = [
    "/", "/contact", "/contact-us", "/about", "/about-us", "/team", "/staff", "/services", "/book",
    "/booking", "/appointment", "/appointments", "/schedule", "/request-quote", "/free-estimate",
    "/new-patient", "/locations",
]
CHATBOT_MARKERS = ["intercom", "drift", "livechat", "live chat", "tawk.to", "zendesk", "crisp.chat", "chat widget"]
BOOKING_MARKERS = ["online booking", "book online", "schedule online", "request appointment", "book an appointment"]


def detect_platform(html: str) -> str:
    low = html.lower()
    markers = {
        "WordPress": ["wp-content", "wordpress"],
        "Wix": ["wixstatic", "wix.com"],
        "Squarespace": ["squarespace"],
        "Webflow": ["webflow"],
        "Shopify": ["cdn.shopify", "shopify"],
    }
    for platform, values in markers.items():
        if any(value in low for value in values):
            return platform
    return ""


def _clean_url(url: str) -> str:
    return urldefrag(ensure_http_url(url))[0].rstrip("/") or ensure_http_url(url)


def _candidate_links(soup: BeautifulSoup, page: str, domain: str) -> List[str]:
    root_domain = registrable_domain(domain)
    links: List[str] = []
    for a in soup.select("a[href]"):
        href = _clean_url(urljoin(page, a.get("href", "")))
        parsed = urlparse(href)
        if parsed.scheme not in {"http", "https"}:
            continue
        if registrable_domain(href) != root_domain:
            continue
        text = (a.get_text(" ", strip=True) + " " + href).lower()
        if any(k in text for k in KEYWORDS) and href not in links:
            links.append(href)
    return links


def crawl_site(url: str, max_pages: int | None = None) -> Dict[str, str]:
    max_pages = max_pages or int(os.getenv("MAX_PAGES_PER_SITE", "10"))
    delay = float(os.getenv("CRAWL_DELAY_SECONDS", "2"))
    timeout = float(os.getenv("REQUEST_TIMEOUT_SECONDS", "12"))
    user_agent = os.getenv("APP_USER_AGENT", "DreamProtocolLeadResearch/1.0 contact: hello@dreamprotocol.ai")
    start_url = _clean_url(url)
    domain = normalize_domain(start_url)
    root_domain = registrable_domain(start_url)
    to_visit = [start_url]
    for path in COMMON_PATHS:
        candidate = _clean_url(urljoin(start_url, path))
        if candidate not in to_visit:
            to_visit.append(candidate)

    visited: Set[str] = set()
    emails: List[str] = []
    phones: List[str] = []
    contact_page = booking_page = quote_page = ""
    contact_form = chatbot = booking = False
    platform = ""
    session = requests.Session()
    session.headers.update({"User-Agent": user_agent, "Accept": "text/html,application/xhtml+xml"})

    while to_visit and len(visited) < max_pages:
        page = to_visit.pop(0)
        if page in visited or registrable_domain(page) != root_domain:
            continue
        visited.add(page)
        try:
            r = session.get(page, timeout=timeout)
            if r.status_code >= 400:
                continue
            content_type = r.headers.get("content-type", "").lower()
            if "text/html" not in content_type and "application/xhtml" not in content_type and content_type:
                continue
            html = r.text
        except Exception as exc:
            print(f"[CRAWL] Failed {page}: {exc}", flush=True)
            continue

        low_html = html.lower()
        platform = platform or detect_platform(html)
        extracted = extract_contacts(html)
        emails.extend(extracted["emails"])
        phones.extend(extracted["phones"])

        soup = BeautifulSoup(html, "html.parser")
        if soup.select("form"):
            contact_form = True
        if any(marker in low_html for marker in CHATBOT_MARKERS):
            chatbot = True
        if any(marker in low_html for marker in BOOKING_MARKERS):
            booking = True

        path_text = page.lower()
        if "contact" in path_text and not contact_page:
            contact_page = page
        if any(k in path_text for k in ["book", "booking", "appointment", "schedule"]) and not booking_page:
            booking_page = page
            booking = True
        if any(k in path_text for k in ["quote", "estimate"]) and not quote_page:
            quote_page = page

        for href in _candidate_links(soup, page, domain):
            text = href.lower()
            if "contact" in text and not contact_page:
                contact_page = href
            if any(k in text for k in ["book", "booking", "appointment", "schedule"]) and not booking_page:
                booking_page = href
            if any(k in text for k in ["quote", "estimate"]) and not quote_page:
                quote_page = href
            if href not in visited and href not in to_visit and len(visited) + len(to_visit) < max_pages + len(KEYWORDS):
                to_visit.append(href)

        if to_visit and len(visited) < max_pages:
            time.sleep(delay)

    email_result = filter_emails(emails, domain)
    return {
        "website": start_url,
        "domain": domain,
        "emails": ";".join(email_result["good"]),
        "junk_emails": ";".join(email_result["junk"]),
        "phones": ";".join(sorted(set(phones))),
        "contact_page_url": contact_page,
        "booking_page_url": booking_page,
        "quote_page_url": quote_page,
        "contact_form_present": str(contact_form),
        "chatbot_present": str(chatbot),
        "online_booking_present": str(booking or bool(booking_page)),
        "platform": platform,
        "pages_crawled": str(len(visited)),
    }


def crawl_discovered_websites() -> List[Dict[str, str]]:
    seeds = read_csv(DATA_DIR / "marin_discovered_websites.csv")
    out = []
    total = len(seeds)
    for index, s in enumerate(seeds, start=1):
        site = s.get("website", "")
        if not site:
            continue
        print(f"[CRAWL] Crawling {index}/{total}: {site}", flush=True)
        row = {**s, **crawl_site(site)}
        out.append(row)
    output_path = DATA_DIR / "marin_crawled_websites.csv"
    write_csv(output_path, out)
    print(f"[CRAWL] Wrote {output_path} with {len(out)} crawled websites", flush=True)
    return out
