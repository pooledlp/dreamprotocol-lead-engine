from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

import requests
from bs4 import BeautifulSoup

from .utils import DATA_DIR, dedupe_records, is_directory, is_social, likely_marin, normalize_domain, read_csv, write_csv

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
    "{city} {category} appointment",
    "{city} {category} request quote",
    "{city} {category} official website",
    "{category} in {city} CA",
]


@dataclass
class DiscoveryProvider:
    name: str
    enabled: bool = False

    def search(self, query: str) -> List[Dict[str, str]]:
        return []


class DuckDuckGoHtmlProvider(DiscoveryProvider):
    def __init__(self) -> None:
        super().__init__(name="duckduckgo_html", enabled=True)

    def search(self, query: str) -> List[Dict[str, str]]:
        url = "https://duckduckgo.com/html/"
        resp = requests.get(url, params={"q": query}, timeout=20)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        rows = []
        for r in soup.select(".result")[:10]:
            link = r.select_one("a.result__a")
            snippet = r.select_one(".result__snippet")
            href = link.get("href", "") if link else ""
            rows.append({
                "business_name": link.get_text(strip=True) if link else "",
                "website": href,
                "listing_url": href,
                "snippet": snippet.get_text(" ", strip=True) if snippet else "",
                "provider": self.name,
            })
        return rows


class DisabledBraveProvider(DiscoveryProvider):
    def __init__(self):
        super().__init__(name="brave_api", enabled=False)


class DisabledGoogleCSEProvider(DiscoveryProvider):
    def __init__(self):
        super().__init__(name="google_cse", enabled=False)


def generate_queries() -> List[Dict[str, str]]:
    return [
        {"city": city, "category": category, "query": pattern.format(city=city, category=category)}
        for city in CITIES
        for category in CATEGORIES
        for pattern in QUERY_PATTERNS
    ]


def discover_marin_websites() -> List[Dict[str, str]]:
    providers = [DuckDuckGoHtmlProvider(), DisabledBraveProvider(), DisabledGoogleCSEProvider()]
    discovered: List[Dict[str, str]] = []

    for q in generate_queries():
        for provider in providers:
            if not provider.enabled:
                continue
            try:
                results = provider.search(q["query"])
            except Exception:
                continue
            for row in results:
                website = row.get("website", "")
                if not website:
                    continue
                if is_social(website):
                    continue
                domain = normalize_domain(website)
                row.update({"city": q["city"], "category": q["category"], "domain": domain})
                if is_directory(website) and row.get("snippet"):
                    continue
                if not likely_marin(f"{q['city']} {row.get('snippet', '')} {row.get('business_name', '')}"):
                    continue
                discovered.append(row)

    manual = read_csv(DATA_DIR / "websites.csv")
    for m in manual:
        m.setdefault("provider", "manual")
        m.setdefault("listing_url", m.get("website", ""))
        m.setdefault("domain", normalize_domain(m.get("website", "")))
    discovered.extend(manual)

    discovered = dedupe_records(discovered)
    write_csv(DATA_DIR / "marin_discovered_websites.csv", discovered)
    return discovered
