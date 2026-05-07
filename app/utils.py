import csv
import hashlib
import os
import re
from pathlib import Path
from typing import Dict, Iterable, List
from urllib.parse import urlparse

DATA_DIR = Path(os.getenv("DATA_DIR", "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

SOCIAL_DOMAINS = {
    "facebook.com",
    "instagram.com",
    "x.com",
    "twitter.com",
    "linkedin.com",
    "tiktok.com",
    "youtube.com",
    "yelp.com",
}

DIRECTORY_DOMAINS = {
    "yellowpages.com",
    "mapquest.com",
    "superpages.com",
    "manta.com",
    "chamberofcommerce.com",
    "bbb.org",
    "angi.com",
    "angieslist.com",
    "homeadvisor.com",
    "thumbtack.com",
    "opencare.com",
    "zocdoc.com",
    "healthgrades.com",
    "tripadvisor.com",
    "booking.com",
    "mapcarta.com",
}


def ensure_http_url(url: str) -> str:
    if not url:
        return ""
    cleaned = url.strip()
    if cleaned.startswith("//"):
        return f"https:{cleaned}"
    if cleaned.startswith(("http://", "https://")):
        return cleaned
    return f"https://{cleaned}"


def normalize_domain(url: str) -> str:
    if not url:
        return ""
    parsed = urlparse(ensure_http_url(url))
    host = parsed.netloc.lower().strip()
    if host.startswith("www."):
        host = host[4:]
    return host.split(":", 1)[0]




def registrable_domain(url_or_domain: str) -> str:
    domain = normalize_domain(url_or_domain)
    if not domain:
        return ""
    parts = domain.split(".")
    if len(parts) <= 2:
        return domain
    two_part_suffixes = {"co.uk", "com.au", "com.br", "co.nz", "com.mx"}
    suffix = ".".join(parts[-2:])
    if suffix in two_part_suffixes and len(parts) >= 3:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:])


def is_social(url: str) -> bool:
    domain = normalize_domain(url)
    return any(domain.endswith(d) for d in SOCIAL_DOMAINS)


def is_directory(url: str) -> bool:
    domain = normalize_domain(url)
    return any(domain.endswith(d) for d in DIRECTORY_DOMAINS)


MARIN_TERMS = {
    "marin",
    "san rafael",
    "novato",
    "mill valley",
    "sausalito",
    "larkspur",
    "corte madera",
    "tiburon",
    "san anselmo",
    "fairfax",
    "greenbrae",
    "kentfield",
    "ross",
    "belvedere",
    "point reyes",
    "marin city",
}


def likely_marin(text: str) -> bool:
    if not text:
        return False
    t = text.lower()
    return any(term in t for term in MARIN_TERMS) or " ca" in t or "california" in t


def slug_id(*parts: str) -> str:
    return hashlib.md5("|".join(parts).encode("utf-8")).hexdigest()[:12]


def dedupe_records(records: Iterable[Dict[str, str]]) -> List[Dict[str, str]]:
    seen = set()
    output = []
    for row in records:
        key = normalize_domain(row.get("website", ""))
        if not key or key in seen:
            continue
        seen.add(key)
        output.append(row)
    return output


def read_csv(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: List[Dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields = sorted({k for r in rows for k in r.keys()})
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def clean_text(value: str) -> str:
    if not value:
        return ""
    return re.sub(r"\s+", " ", value).strip()
