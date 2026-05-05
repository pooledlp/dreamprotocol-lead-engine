import re
from typing import Dict, List, Set

from bs4 import BeautifulSoup

JUNK_FRAGMENTS = [
    "example.com", "domain.com", "wordpress.com", "wix.com", "squarespace.com", "godaddy", "namecheap",
    "cloudflare", "sentry", "schema.org", "noreply", "no-reply", "abuse", "privacy", "hostmaster",
]
COMMON_GOOD = {"info", "hello", "contact", "office", "admin", "appointments", "sales", "support", "manager", "frontdesk"}

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"(?:\+1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}")


def extract_contacts(html: str) -> Dict[str, List[str]]:
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(" ", strip=True)

    mailtos: Set[str] = {a.get("href", "").replace("mailto:", "").split("?")[0] for a in soup.select('a[href^="mailto:"]')}
    visibles: Set[str] = set(EMAIL_RE.findall(text))
    schema_text = " ".join([s.get_text(" ", strip=True) for s in soup.select('script[type="application/ld+json"]')])
    schema_emails = set(EMAIL_RE.findall(schema_text))

    tel_links = {a.get("href", "").replace("tel:", "") for a in soup.select('a[href^="tel:"]')}
    phones = set(PHONE_RE.findall(text)) | tel_links

    emails = list({e.lower() for e in (mailtos | visibles | schema_emails) if e})
    phones_clean = sorted({p.strip() for p in phones if p})
    return {"emails": sorted(emails), "phones": phones_clean}


def filter_emails(emails: List[str], domain: str) -> Dict[str, List[str]]:
    good, junk = [], []
    same_domain = []
    free_domains = ("gmail.com", "outlook.com", "yahoo.com")
    for email in emails:
        e = email.lower()
        if any(x in e for x in JUNK_FRAGMENTS):
            junk.append(email)
            continue
        local, _, host = e.partition("@")
        if host == domain or host.endswith("." + domain):
            same_domain.append(email)
            good.append(email)
            continue
        if host in free_domains:
            if same_domain:
                junk.append(email)
            else:
                good.append(email)
            continue
        if local in COMMON_GOOD:
            good.append(email)
        else:
            junk.append(email)
    return {"good": sorted(set(good)), "junk": sorted(set(junk))}
