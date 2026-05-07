import csv
import hashlib
import json
import os
import re
from difflib import SequenceMatcher
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List
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


BAY_AREA_TERMS = {
    "bay area", "marin", "north bay", "east bay", "peninsula", "south bay", "san francisco",
    "san rafael", "novato", "mill valley", "sausalito", "petaluma", "napa", "sonoma", "santa rosa",
    "oakland", "berkeley", "alameda", "walnut creek", "concord", "fremont", "hayward",
    "dublin", "pleasanton", "livermore", "richmond",
    "san mateo", "burlingame", "redwood city", "palo alto", "menlo park", "mountain view",
    "san jose", "santa clara", "sunnyvale", "cupertino", "campbell", "los gatos",
}


def likely_bay_area(text: str) -> bool:
    if not text:
        return False
    t = text.lower()
    return any(term in t for term in BAY_AREA_TERMS) or " ca" in t or "california" in t


def likely_marin(text: str) -> bool:
    return likely_bay_area(text)


def slug_id(*parts: str) -> str:
    return hashlib.md5("|".join(parts).encode("utf-8")).hexdigest()[:12]


def normalize_phone(value: str) -> str:
    digits = re.sub(r"\D", "", value or "")
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    if len(digits) != 10:
        return ""
    return f"{digits[:3]}-{digits[3:6]}-{digits[6:]}"


def normalize_phone_list(values: Iterable[str] | str) -> List[str]:
    if isinstance(values, str):
        parts = re.split(r"[;,|]\s*", values)
    else:
        parts = list(values)
    return sorted({phone for phone in (normalize_phone(part) for part in parts) if phone})


def normalize_business_name(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9 ]+", " ", (value or "").lower())
    cleaned = re.sub(r"\b(inc|llc|corp|corporation|company|co|the|official|website|home)\b", " ", cleaned)
    return clean_text(cleaned)


def _business_name_similar(left: str, right: str) -> bool:
    left_name = normalize_business_name(left)
    right_name = normalize_business_name(right)
    if not left_name or not right_name:
        return False
    return SequenceMatcher(None, left_name, right_name).ratio() >= 0.88


def dedupe_records(records: Iterable[Dict[str, str]]) -> List[Dict[str, str]]:
    seen_domains = set()
    seen_phones = set()
    output = []
    for row in records:
        key = normalize_domain(row.get("website", ""))
        phones = set(normalize_phone_list(row.get("primary_phone") or row.get("phones", "")))
        name = row.get("business_name", "")
        if key and key in seen_domains:
            continue
        if phones and phones & seen_phones:
            continue
        if any(_business_name_similar(name, existing.get("business_name", "")) for existing in output):
            continue
        if key:
            seen_domains.add(key)
        seen_phones.update(phones)
        if phones and not row.get("primary_phone"):
            row["primary_phone"] = sorted(phones)[0]
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



def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def save_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(path)
