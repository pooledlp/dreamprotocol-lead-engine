from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Dict, List
from urllib.parse import urlparse

import requests

from .utils import (
    DATA_DIR,
    dedupe_records,
    ensure_http_url,
    is_directory,
    is_social,
    likely_marin,
    normalize_domain,
    read_csv,
    write_csv,
)

CITIES = [
    "San Rafael", "Novato", "Mill Valley", "Sausalito", "Larkspur", "Corte Madera", "Tiburon",
    "San Anselmo", "Fairfax", "Greenbrae", "Kentfield", "Ross", "Belvedere", "Point Reyes", "Marin City",
]

CATEGORIES = [
    "dentist", "dental office", "med spa", "chiropractor", "veterinary clinic", "HVAC", "plumber",
    "electrician", "roofer", "contractor", "property management", "real estate office", "law firm", "CPA",
    "accounting firm", "insurance agency", "restaurant", "catering", "hotel", "salon", "spa", "fitness gym",
    "private school", "tutoring",
]

QUERY_PATTERNS = [
    "{city} {category} contact",
    "{city} {category} official website",
    "{category} in {city} CA",
]

JSON_ERROR = "[DISCOVER] SearXNG JSON failed. Check searxng/settings.yml has search.formats html and json."


@dataclass
class SearXNGProvider:
    name: str = "searxng"

    def __post_init__(self) -> None:
        self.base_url = os.getenv("SEARXNG_BASE_URL", "http://searxng:8080").rstrip("/")
        self.timeout = float(os.getenv("REQUEST_TIMEOUT_SECONDS", "12"))
        self.max_results = int(os.getenv("MAX_RESULTS_PER_QUERY", "10"))
        self.user_agent = os.getenv(
            "APP_USER_AGENT",
            "DreamProtocolLeadResearch/1.0 contact: hello@dreamprotocol.ai",
        )

    def search(self, query: str) -> List[Dict[str, str]]:
        url = f"{self.base_url}/search"
        try:
            resp = requests.get(
                url,
                params={"q": query, "format": "json", "language": "en", "safesearch": "0"},
                headers={"User-Agent": self.user_agent, "Accept": "application/json"},
                timeout=self.timeout,
            )
            content_type = resp.headers.get("content-type", "").lower()
            if resp.status_code == 403 or "json" not in content_type:
                print(JSON_ERROR, flush=True)
                print(f"[DISCOVER] SearXNG returned status={resp.status_code} content-type={content_type}", flush=True)
                return []
            resp.raise_for_status()
            payload = resp.json()
        except ValueError as exc:
            print(JSON_ERROR, flush=True)
            print(f"[DISCOVER] Non-JSON response for query '{query}': {exc}", flush=True)
            return []
        except requests.RequestException as exc:
            print(f"[DISCOVER] SearXNG request failed for query '{query}': {exc}", flush=True)
            return []
        except Exception as exc:
            print(f"[DISCOVER] Unexpected SearXNG error for query '{query}': {exc}", flush=True)
            return []

        rows = []
        for result in payload.get("results", [])[: self.max_results]:
            result_url = result.get("url") or result.get("href") or ""
            if not result_url:
                continue
            rows.append({
                "business_name": result.get("title", ""),
                "website": result_url,
                "listing_url": result_url,
                "snippet": result.get("content") or result.get("snippet") or "",
                "provider": self.name,
            })
        return rows


def generate_queries() -> List[Dict[str, str]]:
    return [
        {"city": city, "category": category, "query": pattern.format(city=city, category=category)}
        for city in CITIES
        for category in CATEGORIES
        for pattern in QUERY_PATTERNS
    ]


def _looks_like_business_site(row: Dict[str, str], city: str) -> bool:
    website = row.get("website", "")
    domain = normalize_domain(website)
    if not domain:
        return False
    if is_social(website):
        return False
    if is_directory(website):
        return False
    path = urlparse(website).path.lower()
    if domain.endswith("yelp.com") and path:
        return False
    text = f"{city} {row.get('business_name', '')} {row.get('snippet', '')} {website}"
    return likely_marin(text)


def discover_marin_websites() -> List[Dict[str, str]]:
    provider = SearXNGProvider()
    all_queries = generate_queries()
    max_queries = int(os.getenv("MAX_DISCOVERY_QUERIES_PER_RUN", "30"))
    queries = all_queries[:max_queries]
    print(f"[DISCOVER] Generated {len(all_queries)} possible queries, running first {len(queries)}", flush=True)

    discovered: List[Dict[str, str]] = []
    seen_domains = set()

    for index, q in enumerate(queries, start=1):
        print(f"[DISCOVER] Searching {index}/{len(queries)}: {q['query']}", flush=True)
        results = provider.search(q["query"])
        print(f"[DISCOVER] Found {len(results)} results", flush=True)
        for row in results:
            website = ensure_http_url(row.get("website", ""))
            row["website"] = website
            domain = normalize_domain(website)
            if domain in seen_domains:
                continue
            if not _looks_like_business_site(row, q["city"]):
                continue
            row.update({"city": q["city"], "category": q["category"], "domain": domain})
            discovered.append(row)
            seen_domains.add(domain)
            print(f"[DISCOVER] Added domain {domain}", flush=True)

    manual = read_csv(DATA_DIR / "websites.csv")
    for m in manual:
        website = ensure_http_url(m.get("website", ""))
        domain = normalize_domain(website)
        if not website or domain in seen_domains or is_social(website) or is_directory(website):
            continue
        m["website"] = website
        m.setdefault("provider", "manual")
        m.setdefault("listing_url", website)
        m.setdefault("domain", domain)
        discovered.append(m)
        seen_domains.add(domain)
        print(f"[DISCOVER] Added domain {domain}", flush=True)

    discovered = dedupe_records(discovered)
    output_path = DATA_DIR / "marin_discovered_websites.csv"
    write_csv(output_path, discovered)
    print(f"[DISCOVER] Wrote {output_path} with {len(discovered)} discovered websites", flush=True)
    return discovered
