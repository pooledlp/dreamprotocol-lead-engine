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
}


def normalize_domain(url: str) -> str:
    if not url:
        return ""
    parsed = urlparse(url if url.startswith(("http://", "https://")) else f"https://{url}")
    host = parsed.netloc.lower().strip()
    if host.startswith("www."):
        host = host[4:]
    return host


def is_social(url: str) -> bool:
    domain = normalize_domain(url)
    return any(domain.endswith(d) for d in SOCIAL_DOMAINS)


def is_directory(url: str) -> bool:
    domain = normalize_domain(url)
    return any(domain.endswith(d) for d in DIRECTORY_DOMAINS)


def likely_marin(text: str) -> bool:
    if not text:
        return False
    t = text.lower()
    return "marin" in t or "ca" in t or "california" in t


def slug_id(*parts: str) -> str:
    return hashlib.md5("|".join(parts).encode("utf-8")).hexdigest()[:12]


def dedupe_records(records: Iterable[Dict[str, str]]) -> List[Dict[str, str]]:
    seen = set()
    output = []
    for row in records:
        key = (normalize_domain(row.get("website", "")), row.get("business_name", "").strip().lower())
        if key in seen:
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
