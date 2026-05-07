from __future__ import annotations

import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Set
from urllib.parse import urldefrag, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from .extractors import extract_contacts, filter_emails
from .utils import (
    DATA_DIR,
    dedupe_records,
    ensure_http_url,
    load_json,
    normalize_domain,
    normalize_phone_list,
    read_csv,
    registrable_domain,
    save_json,
    utc_now_iso,
    write_csv,
)

KEYWORDS = [
    "contact", "about", "team", "staff", "service", "services", "book", "booking", "appointment",
    "schedule", "quote", "estimate", "patient", "location", "emergency", "maintenance",
]
COMMON_PATHS = [
    "/", "/contact", "/contact-us", "/about", "/about-us", "/team", "/staff", "/services", "/book",
    "/booking", "/appointment", "/appointments", "/schedule", "/request-quote", "/free-estimate",
    "/new-patient", "/locations", "/emergency", "/maintenance-request",
]
CHATBOT_MARKERS = ["intercom", "drift", "livechat", "live chat", "tawk.to", "zendesk", "crisp.chat", "chat widget"]
BOOKING_MARKERS = ["online booking", "book online", "schedule online", "request appointment", "book an appointment"]
QUOTE_MARKERS = ["free estimate", "request a quote", "get a quote", "quote request", "emergency service", "24/7"]


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
    max_pages = max_pages or int(os.getenv("MAX_PAGES_PER_SITE", "8"))
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
    contact_form = chatbot = booking = quote_heavy = emergency = False
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
        if any(marker in low_html for marker in QUOTE_MARKERS):
            quote_heavy = True
        if "emergency" in low_html or "24/7" in low_html or "24 hour" in low_html:
            emergency = True

        path_text = page.lower()
        if "contact" in path_text and not contact_page:
            contact_page = page
        if any(k in path_text for k in ["book", "booking", "appointment", "schedule"]) and not booking_page:
            booking_page = page
            booking = True
        if any(k in path_text for k in ["quote", "estimate"]) and not quote_page:
            quote_page = page
            quote_heavy = True

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
    normalized_phones = normalize_phone_list(phones)
    return {
        "website": start_url,
        "domain": domain,
        "emails": ";".join(email_result["good"]),
        "junk_emails": ";".join(email_result["junk"]),
        "phones": ";".join(normalized_phones),
        "primary_phone": normalized_phones[0] if normalized_phones else "",
        "contact_page_url": contact_page,
        "booking_page_url": booking_page,
        "quote_page_url": quote_page,
        "contact_form_present": str(contact_form),
        "chatbot_present": str(chatbot),
        "online_booking_present": str(booking or bool(booking_page)),
        "quote_language_present": str(quote_heavy or bool(quote_page)),
        "emergency_language_present": str(emergency),
        "phone_count": str(len(normalized_phones)),
        "platform": platform,
        "pages_crawled": str(len(visited)),
        "last_crawled_at": utc_now_iso(),
    }


def _parse_iso(value: str) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _recently_crawled(domain: str, state: Dict[str, Dict[str, str]], recrawl_days: int) -> bool:
    crawled_at = _parse_iso(state.get(domain, {}).get("last_crawled_at", ""))
    if not crawled_at:
        return False
    return datetime.now(timezone.utc) - crawled_at < timedelta(days=recrawl_days)


def _crawl_one(seed: Dict[str, str]) -> Dict[str, str]:
    site = seed.get("website", "")
    print(f"[CRAWL] Starting {site}", flush=True)
    result = crawl_site(site)
    print(f"[EXTRACT] {result.get('domain')} emails={bool(result.get('emails'))} phones={result.get('phone_count', '0')}", flush=True)
    return {**seed, **result}


def crawl_discovered_websites() -> List[Dict[str, str]]:
    seeds = read_csv(DATA_DIR / "bayarea_discovered_websites.csv") or read_csv(DATA_DIR / "marin_discovered_websites.csv")
    existing = read_csv(DATA_DIR / "bayarea_crawled_websites.csv") or read_csv(DATA_DIR / "marin_crawled_websites.csv")
    crawled_state = load_json(DATA_DIR / "crawled_domains.json", {})
    failed_state = load_json(DATA_DIR / "failed_domains.json", {})
    progress = load_json(DATA_DIR / "crawl_progress.json", {})
    recrawl_days = int(os.getenv("DOMAIN_RECRAWL_DAYS", "30"))
    max_domains = int(os.getenv("MAX_DOMAINS_PER_RUN", "500"))
    max_workers = int(os.getenv("MAX_CONCURRENT_CRAWLS", "5"))

    out_by_domain = {normalize_domain(r.get("website", "")): r for r in existing if r.get("website")}
    pending: List[Dict[str, str]] = []
    skipped = 0
    for seed in seeds:
        site = seed.get("website", "")
        domain = normalize_domain(site)
        if not site or not domain:
            continue
        if domain in out_by_domain and _recently_crawled(domain, crawled_state, recrawl_days):
            skipped += 1
            continue
        pending.append(seed)
        if len(pending) >= max_domains:
            break

    total = len(pending)
    print(f"[CRAWL] Loaded {len(seeds)} discovered domains; skipped {skipped} recently crawled; queued {total}", flush=True)
    completed = 0
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_seed = {executor.submit(_crawl_one, seed): seed for seed in pending}
        for future in as_completed(future_to_seed):
            seed = future_to_seed[future]
            domain = normalize_domain(seed.get("website", ""))
            completed += 1
            try:
                row = future.result()
                row_domain = normalize_domain(row.get("website", ""))
                out_by_domain[row_domain] = row
                crawled_state[row_domain] = {"last_crawled_at": row.get("last_crawled_at", utc_now_iso())}
                failed_state.pop(row_domain, None)
            except Exception as exc:
                failed_state[domain] = {"last_failed_at": utc_now_iso(), "error": str(exc), "website": seed.get("website", "")}
                print(f"[CRAWL] Failed domain {domain}: {exc}", flush=True)
            progress["crawl"] = {"completed_this_run": completed, "queued_this_run": total}
            save_json(DATA_DIR / "crawled_domains.json", crawled_state)
            save_json(DATA_DIR / "failed_domains.json", failed_state)
            save_json(DATA_DIR / "crawl_progress.json", progress)
            checkpoint_rows = dedupe_records(out_by_domain.values())
            write_csv(DATA_DIR / "bayarea_crawled_websites.csv", checkpoint_rows)
            print(f"[CRAWL] {completed}/{total}", flush=True)

    out = dedupe_records(out_by_domain.values())
    output_path = DATA_DIR / "bayarea_crawled_websites.csv"
    write_csv(output_path, out)
    # Backward-compatible output for existing Marin workflows.
    write_csv(DATA_DIR / "marin_crawled_websites.csv", out)
    print(f"[CRAWL] Wrote {output_path} with {len(out)} crawled websites", flush=True)
    return out
