"""Command-line tourism data rebuild/refresh utility.

Examples:
    python -m scripts.refresh_data                    # refresh from every source
    python -m scripts.refresh_data --reset            # rebuild places from scratch
    python -m scripts.refresh_data --sources ttdc osm # only some sources
    python -m scripts.refresh_data --skip hrce --json report.json
"""

import argparse
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from database.connection import initialize_database  # noqa: E402
from services.data_updates import SOURCE_KEYS, refresh_tourism_data  # noqa: E402


def _print_report(report):
    print("\nSource results")
    print("-" * 78)
    for key, result in report["sources"].items():
        detail = result["error"] or (f"{len(result['warnings'])} warning(s)" if result["warnings"] else "")
        print(f"  {key:<17} {result['status']:<8} {result['rows']:>6} rows {result['seconds']:>7.1f}s  {detail}")
        for warning in result["warnings"][:5]:
            print(f"      - {warning}")
        if len(result["warnings"]) > 5:
            print(f"      ... and {len(result['warnings']) - 5} more")
    print("-" * 78)
    for key in ("records_seen", "records_merged", "places_inserted", "places_updated", "images_written",
                "festivals_written", "holidays_written", "junk_places_removed", "cross_district_duplicates_merged", "spelling_duplicates_merged",
                "places_total",
                "places_with_coordinates", "districts_covered", "seconds"):
        print(f"  {key.replace('_', ' '):<26} {report.get(key)}")


def main():
    parser = argparse.ArgumentParser(description="Collect Smart Tamilnadu Tourism data")
    parser.add_argument("--reset", action="store_true", help="Clear collected tourism records before rebuilding")
    parser.add_argument("--sources", nargs="+", choices=SOURCE_KEYS, help="Only run these sources")
    parser.add_argument("--skip", nargs="+", choices=SOURCE_KEYS, default=(), help="Sources to leave out")
    parser.add_argument("--osm-budget", type=float, metavar="MINUTES",
                        help="Time limit for OpenStreetMap collection (default 25); unfinished districts "
                             "use cached data and are fetched on the next run")
    parser.add_argument("--json", metavar="PATH", help="Also write the full report as JSON")
    parser.add_argument("--verbose", "-v", action="store_true", help="Log every HTTP request")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s", datefmt="%H:%M:%S",
    )
    if not args.verbose:
        for noisy in ("urllib3", "charset_normalizer"):
            logging.getLogger(noisy).setLevel(logging.WARNING)

    initialize_database()

    options = {"osm": {"time_budget": args.osm_budget * 60}} if args.osm_budget else None
    report = refresh_tourism_data(sources=args.sources, skip=args.skip, source_options=options,
                                  reset=args.reset)
    _print_report(report)
    if args.json:
        Path(args.json).write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    failed = [key for key, result in report["sources"].items() if result["status"] == "failed"]
    return 1 if failed and len(failed) == len(report["sources"]) else 0


if __name__ == "__main__":
    sys.exit(main())
