# DreamProtocol Lead Engine (Marin County + SearXNG)

DreamProtocol Lead Engine discovers Marin County business websites through a self-hosted SearXNG service, crawls public business websites, extracts public contact signals, scores leads, and exports CSVs.

## Safety and scope

- 100% free discovery stack; no paid search APIs.
- Self-hosted SearXNG is queried locally from Docker Compose.
- Public business websites only.
- No social media scraping.
- No login bypass.
- No email sending.
- Crawl delays, request timeouts, user-agent configuration, and progress logging are built in.

## Architecture

1. Docker Compose starts `searxng` with JSON output enabled.
2. `marin-lead-engine` calls `http://searxng:8080/search?q=...&format=json`.
3. Discovery generates Marin County city/category queries and keeps likely official business websites.
4. The crawler visits each discovered site, stays on the same domain, follows useful public pages, and extracts contact signals.
5. Exports write CSVs into `data/`.

## SearXNG JSON configuration

`searxng/settings.yml` must include JSON as an enabled search format:

```yaml
use_default_settings: true
server:
  secret_key: "replace-with-random-secret"
  limiter: false
  image_proxy: false
search:
  formats:
    - html
    - json
```

If JSON is not enabled, the app prints this fix message:

```text
[DISCOVER] SearXNG JSON failed. Check searxng/settings.yml has search.formats html and json.
```

## Environment variables

Copy `.env.example` to `.env` before running in Docker:

```bash
cp .env.example .env
```

Important defaults:

```env
SEARXNG_BASE_URL=http://searxng:8080
DISCOVERY_PROVIDER=searxng
MAX_DISCOVERY_QUERIES_PER_RUN=30
MAX_RESULTS_PER_QUERY=10
MAX_PAGES_PER_SITE=10
CRAWL_DELAY_SECONDS=2
REQUEST_TIMEOUT_SECONDS=12
APP_USER_AGENT=DreamProtocolLeadResearch/1.0 contact: hello@dreamprotocol.ai
```

## Commands

From a local Python environment:

```bash
python -m app.main discover-marin
python -m app.main crawl-websites
python -m app.main export
python -m app.main marin-run-all
```

`marin-run-all` waits up to 60 seconds for SearXNG JSON search to become reachable, then runs discovery, crawling, and export.

## Docker / Linode runbook

Run these commands on the Linode VM from the repo directory:

```bash
git pull
cp .env.example .env
docker compose down
docker compose build --no-cache
docker compose up -d searxng
docker compose logs -f searxng
docker compose run --rm -T marin-lead-engine
```

Check generated CSVs:

```bash
find data -maxdepth 1 -type f -name "*.csv" -ls
head -20 data/marin_high_score_leads.csv
```

Download the high-score leads CSV from Windows PowerShell:

```powershell
scp -i C:\WINDOWS\system32\y root@YOUR_LINODE_IP:/opt/dreamprotocol-lead-engine/data/marin_high_score_leads.csv "$env:USERPROFILE\Downloads\marin_high_score_leads.csv"
```

## CSV outputs

- `data/marin_discovered_websites.csv`
- `data/marin_all_leads.csv`
- `data/marin_email_leads.csv`
- `data/marin_high_score_leads.csv`
- `data/marin_no_email_contact_form_leads.csv`
- `data/marin_junk_filtered_emails.csv`

## Discovery logging

Expected progress logs look like:

```text
[DISCOVER] Generated 1080 possible queries, running first 30
[DISCOVER] Searching 1/30: San Rafael dentist contact
[DISCOVER] Found 8 results
[DISCOVER] Added domain example.com
[DISCOVER] Wrote data/marin_discovered_websites.csv with 42 discovered websites
[CRAWL] Crawling 1/42: https://example.com
[EXPORT] Wrote data/marin_high_score_leads.csv
```

## Lead scoring

- Public email found: +20
- Phone found: +10
- Contact page found: +10
- Contact form found: +10
- No chatbot found: +10
- No online booking found: +10
- High-value category: +20
- Appointment-heavy category: +10
- Quote-heavy category: +10
- Phone-heavy category: +10
- Marin city match: +10

Priority bands:

- Hot: 80+
- Warm: 60-79
- Low: below 60
