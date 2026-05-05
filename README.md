# DreamProtocol Lead Engine (Marin County, Scraping-First)

## What this does
This version automatically discovers Marin County small businesses by city and category, crawls their public websites, extracts public contact signals, scores leads, and exports CSV files.

- No manual seed source file required for v1.
- Optional manual override via `data/websites.csv`.
- No email sending.
- No social media scraping.
- No login bypass.
- Public data only.

## How Marin discovery works
1. The system generates city/category search phrases internally.
2. It builds discovery queries such as:
   - `{city} {category} contact`
   - `{city} {category} appointment`
   - `{city} {category} request quote`
   - `{city} {category} official website`
   - `{category} in {city} CA`
3. It uses a pluggable discovery provider module (`discover_marin.py`).
4. Free v1 default provider: DuckDuckGo HTML endpoint (scrape-friendly public page).
5. Google result pages are not scraped directly.
6. Brave Search API + Google CSE providers are included but disabled by default.
7. Deduping and Marin-likelihood filtering are applied.

## Run
```bash
python app/main.py discover-marin
python app/main.py crawl-websites
python app/main.py export
python app/main.py marin-run-all
```

## Docker
```bash
docker compose build
docker compose run --rm marin-lead-engine python app/main.py marin-run-all
```

- Python 3.12
- CSV storage only
- Output written to `/app/data` in container (mapped to `./data` locally)

## CSV outputs
- `data/marin_all_leads.csv`
- `data/marin_email_leads.csv`
- `data/marin_high_score_leads.csv`
- `data/marin_no_email_contact_form_leads.csv`
- `data/marin_junk_filtered_emails.csv`
- `data/marin_discovered_websites.csv`

## Download CSVs from Linode
If your app runs on a Linode VM:

```bash
scp user@<linode-ip>:/path/to/project/data/*.csv ./
```

Or from inside Docker on the VM:

```bash
docker cp <container_name>:/app/data ./data
```

## Safety notes
- This scraper only targets publicly available pages.
- Do not scrape authenticated/private sections.
- Do not collect sensitive/private personal data.
- Respect site terms, robots policies, and rate limits.
