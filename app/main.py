import sys

from app.crawler import crawl_discovered_websites
from app.discover_marin import discover_marin_websites
from app.exporters import export_all


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("Usage: python app/main.py [discover-marin|crawl-websites|export|marin-run-all]")

    command = sys.argv[1]
    if command == "discover-marin":
        discover_marin_websites()
    elif command == "crawl-websites":
        crawl_discovered_websites()
    elif command == "export":
        export_all()
    elif command == "marin-run-all":
        discover_marin_websites()
        crawl_discovered_websites()
        export_all()
    else:
        raise SystemExit(f"Unknown command: {command}")


if __name__ == "__main__":
    main()
