import os
import sys
import time

import requests

from app.crawler import crawl_discovered_websites
from app.discover_marin import JSON_ERROR, discover_marin_websites
from app.exporters import export_all


def wait_for_searxng(timeout_seconds: int = 60) -> bool:
    base_url = os.getenv("SEARXNG_BASE_URL", "http://searxng:8080").rstrip("/")
    request_timeout = float(os.getenv("REQUEST_TIMEOUT_SECONDS", "12"))
    url = f"{base_url}/search"
    started = time.monotonic()
    attempt = 1
    while time.monotonic() - started < timeout_seconds:
        try:
            print(f"[MAIN] Waiting for SearXNG JSON ({attempt}): {url}", flush=True)
            resp = requests.get(
                url,
                params={"q": "test", "format": "json"},
                headers={"Accept": "application/json"},
                timeout=request_timeout,
            )
            content_type = resp.headers.get("content-type", "").lower()
            if resp.status_code == 200 and "json" in content_type:
                resp.json()
                print("[MAIN] SearXNG JSON is reachable", flush=True)
                return True
            if resp.status_code == 403 or "json" not in content_type:
                print(JSON_ERROR, flush=True)
                print(f"[MAIN] Got status={resp.status_code} content-type={content_type}", flush=True)
            else:
                print(f"[MAIN] SearXNG not ready: status={resp.status_code}", flush=True)
        except ValueError as exc:
            print(JSON_ERROR, flush=True)
            print(f"[MAIN] SearXNG returned non-JSON: {exc}", flush=True)
        except requests.RequestException as exc:
            print(f"[MAIN] SearXNG not reachable yet: {exc}", flush=True)
        attempt += 1
        time.sleep(3)

    print("[MAIN] SearXNG is unreachable after 60 seconds.", flush=True)
    print("[MAIN] Fix: run `docker compose up -d searxng` and verify searxng/settings.yml includes search.formats html and json.", flush=True)
    return False


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("Usage: python -m app.main [discover-marin|crawl-websites|export|marin-run-all]")

    command = sys.argv[1]
    if command == "discover-marin":
        discover_marin_websites()
    elif command == "crawl-websites":
        crawl_discovered_websites()
    elif command == "export":
        export_all()
    elif command == "marin-run-all":
        if not wait_for_searxng():
            raise SystemExit(1)
        discover_marin_websites()
        crawl_discovered_websites()
        export_all()
    else:
        raise SystemExit(f"Unknown command: {command}")


if __name__ == "__main__":
    main()
