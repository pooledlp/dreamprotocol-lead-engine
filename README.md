# DreamProtocol Lead Engine (Bay Area + SearXNG)

DreamProtocol Lead Engine discovers Bay Area SMB websites through a self-hosted SearXNG service, crawls public business websites safely over repeated runs, extracts public contact signals, scores leads, and exports segmented CSVs.

## Safety and scope

- 100% free discovery stack; no paid search APIs.
- Self-hosted SearXNG is queried locally from Docker Compose.
- Public business websites only.
- No social media scraping.
- No login bypass.
- No email sending.
- Crawl delays, request timeouts, user-agent configuration, crawl state, recrawl windows, and progress logging are built in.
- The crawler is designed to scale toward 10,000+ leads over multiple runs without recrawling recently crawled domains.

## Supported regions

Use one of these region slugs with `discover-websites` or `run-region`:

- `north-bay`: San Rafael, Novato, Mill Valley, Sausalito, Petaluma, Napa, Sonoma, Santa Rosa
- `east-bay`: Oakland, Berkeley, Alameda, Walnut Creek, Concord, Fremont, Hayward, Dublin, Pleasanton, Livermore, Richmond
- `peninsula`: San Mateo, Burlingame, Redwood City, Palo Alto, Menlo Park, Mountain View
- `south-bay`: San Jose, Santa Clara, Sunnyvale, Cupertino, Campbell, Los Gatos
- `san-francisco`: San Francisco
- `all-bay-area`: all cities above

`discover-marin` and `marin-run-all` remain available as backward-compatible aliases for the North Bay workflow.

## Architecture

1. Docker Compose starts `searxng` with JSON output enabled.
2. `marin-lead-engine` calls `http://searxng:8080/search?q=...&format=json`.
3. Discovery generates region city/category queries and keeps likely official business websites.
4. The crawler visits each discovered site, stays on the same domain, follows useful public pages, and extracts contact signals.
5. Crawl state is persisted in JSON so interrupted runs can resume and recent domains can be skipped.
6. Exports write CSVs into `data/`.

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

Important safe scaling defaults:

```env
SEARXNG_BASE_URL=http://searxng:8080
DISCOVERY_PROVIDER=searxng
MAX_DISCOVERY_QUERIES_PER_RUN=100
MAX_DOMAINS_PER_RUN=500
MAX_CONCURRENT_CRAWLS=5
MAX_RESULTS_PER_QUERY=10
MAX_PAGES_PER_SITE=8
DOMAIN_RECRAWL_DAYS=30
CRAWL_DELAY_SECONDS=2
REQUEST_TIMEOUT_SECONDS=12
APP_USER_AGENT=DreamProtocolLeadResearch/1.0 contact: hello@dreamprotocol.ai
```

## Commands

From a local Python environment:

```bash
python -m app.main discover-websites north-bay
python -m app.main discover-websites east-bay
python -m app.main discover-websites peninsula
python -m app.main discover-websites south-bay
python -m app.main discover-websites san-francisco
python -m app.main discover-websites all-bay-area
python -m app.main crawl-websites
python -m app.main export
python -m app.main run-region all-bay-area
```

`run-region` waits up to 60 seconds for SearXNG JSON search to become reachable, then runs discovery, crawling, and export.

## Cron automation scripts

Use the checked-in scripts from cron or a shell session:

```bash
scripts/run_north_bay.sh
scripts/run_east_bay.sh
scripts/run_peninsula.sh
scripts/run_south_bay.sh
scripts/run_all_bay_area.sh
```

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
head -20 data/bayarea_hot_leads.csv
```

## State files

These JSON files are written under `data/`:

- `crawled_domains.json`: domains and last crawl timestamps.
- `failed_domains.json`: domains that failed, with error and timestamp.
- `crawl_progress.json`: discovery query cursors and crawl progress counters.

Domains crawled within `DOMAIN_RECRAWL_DAYS` (default `30`) are skipped, which allows repeated cron runs to expand coverage without duplicate crawling.

## CSV outputs

Primary Bay Area exports:

- `data/bayarea_all_leads.csv`
- `data/bayarea_hot_leads.csv`
- `data/bayarea_phone_heavy.csv`
- `data/bayarea_medical.csv`
- `data/bayarea_contractors.csv`
- `data/bayarea_property_management.csv`

Backward-compatible Marin exports are still written:

- `data/marin_discovered_websites.csv`
- `data/marin_all_leads.csv`
- `data/marin_email_leads.csv`
- `data/marin_high_score_leads.csv`
- `data/marin_no_email_contact_form_leads.csv`
- `data/marin_junk_filtered_emails.csv`

## Discovery and crawl logging

Expected progress logs look like:

```text
[DISCOVER] Region=all-bay-area generated 5616 possible queries; resuming at 1, running 100
[DISCOVER] Searching 1/5616: San Rafael dentist contact
[DISCOVER] Found 8 results
[DISCOVER] Added domain example.com
[CRAWL] Loaded 500 discovered domains; skipped 120 recently crawled; queued 380
[CRAWL] Starting https://example.com
[EXTRACT] example.com emails=True phones=2
[CRAWL] 422/10000
[EXPORT] Wrote data/bayarea_hot_leads.csv rows=87
```

## Lead scoring and enrichment

The score boosts signals such as:

- Public email, phone, contact page, and contact forms.
- WordPress/Wix sites.
- No chatbot.
- No online booking.
- Quote-heavy language or quote pages.
- Emergency-service and after-hours language.
- Phone-heavy businesses.
- High-value categories.

The export rows include:

- `business_type`
- `likely_after_hours_opportunity`
- `likely_missed_call_risk`
- `likely_quote_driven`
- `likely_dispatch_driven`

Pain angles are tailored by business type, including emergency-call and dispatch angles for contractors, appointment/intake angles for dental and wellness businesses, and maintenance/tenant/showing coordination angles for property management.
