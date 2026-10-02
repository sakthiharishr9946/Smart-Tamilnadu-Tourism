"""Coordinate enrichment for existing tourism database records.

Multi-phase strategy:
  Phase 0 – Cleanup:   Remove obvious web scraping artifacts.
  Phase 1 – OSM:       Match OSM records (with lat/lon) to DB by name+district.
  Phase 2 – Wikidata:  Match Wikidata records (with lat/lon), filtered to TN bounds.
  Phase 3 – Nominatim: Geocode remaining NULL-coordinate places via Nominatim
                        (rate-limited, batched, smart query construction).

Only latitude and longitude are updated (plus cleanup of junk records in Phase 0).
"""

import argparse
import json
import sys
import time
import re
from pathlib import Path

import pandas as pd

# ── project imports ──────────────────────────────────────────────
sys.path.insert(0, ".")

from database.connection import initialize_database, fetch_all, execute_query
from database.migrations import apply_migrations
from scrapers.tourism import scrape_openstreetmap_tourism, scrape_wikidata_tourism
from services.location.geocoding import geocode_in_district

# ── Tamil Nadu bounding box (generous) ───────────────────────────
TN_LAT_MIN, TN_LAT_MAX = 7.9, 13.7
TN_LON_MIN, TN_LON_MAX = 76.0, 80.6


def _in_tamilnadu(lat, lon):
    """Return True if coordinates fall within Tamil Nadu's bounding box."""
    try:
        lat, lon = float(lat), float(lon)
    except (TypeError, ValueError):
        return False
    return TN_LAT_MIN <= lat <= TN_LAT_MAX and TN_LON_MIN <= lon <= TN_LON_MAX


def _normalize(text):
    """Lowercase, strip, collapse whitespace for matching."""
    if not text:
        return ""
    return re.sub(r"\s+", " ", str(text).strip().lower())


def _db_places_missing_coords():
    """Return DB records that still lack coordinates."""
    rows = fetch_all(
        "SELECT place_id, place_name, district, city_town "
        "FROM places "
        "WHERE latitude IS NULL OR longitude IS NULL "
        # Most prominent places first, so a partial run helps the most.
        "ORDER BY popularity_score DESC, place_id"
    )
    return [dict(r) for r in rows]


def _count_with_coords():
    """Return count of places that already have coordinates."""
    row = fetch_all(
        "SELECT COUNT(*) AS n FROM places "
        "WHERE latitude IS NOT NULL AND longitude IS NOT NULL"
    )
    return row[0]["n"] if row else 0


def _total_places():
    return fetch_all("SELECT COUNT(*) AS n FROM places")[0]["n"]


def _update_coords(place_id, lat, lon):
    """Set latitude and longitude for a single place_id."""
    execute_query(
        "UPDATE places SET latitude=?, longitude=?, updated_at=CURRENT_TIMESTAMP "
        "WHERE place_id=?",
        (float(lat), float(lon), place_id),
    )


# ═══════════════════════════════════════════════════════════════════
# PHASE 0: Clean up web scraping artifacts
# ═══════════════════════════════════════════════════════════════════

JUNK_PLACE_NAMES = {
    "social media links", "site map", "administrative setup", "directory",
    "notices", "media corner", "home", "contact us", "about us", "feedback",
    "downloads", "gallery", "photo gallery", "login", "register",
    "disclaimer", "copyright", "privacy policy", "terms", "media gallery",
    "events & festivals", "accommodation (hotel/resort/dharamsala)",
    "accommodation", "notices", "right to information",
}

JUNK_PATTERNS = [
    r"^→$",                       # bare arrow
    r".+\s*→\s*$",                # "Dindigul →" navigation links
    r"^https?://",                # URLs stored as names
    r"^\d+$",                     # bare numbers
    r"^[^\w\s]+$",                # pure punctuation
]

JUNK_PATTERNS_COMPILED = [re.compile(p, re.IGNORECASE) for p in JUNK_PATTERNS]


def _is_junk_place(name):
    """Return True if this place name is a web scraping artifact."""
    norm = name.strip().lower()
    if norm in JUNK_PLACE_NAMES:
        return True
    if len(norm) <= 2:
        return True
    for pat in JUNK_PATTERNS_COMPILED:
        if pat.match(name.strip()):
            return True
    return False


def cleanup_junk_records():
    """Remove web scraping artifacts from the database."""
    rows = fetch_all("SELECT place_id, place_name FROM places")
    junk_ids = []
    for r in rows:
        if _is_junk_place(r["place_name"]):
            junk_ids.append(r["place_id"])

    if junk_ids:
        placeholders = ",".join(["?"] * len(junk_ids))
        # First delete dependent records
        for table in ["place_features", "place_status", "images", "ratings", "crowd_data"]:
            execute_query(
                f"DELETE FROM {table} WHERE place_id IN ({placeholders})",
                tuple(junk_ids),
            )
        execute_query(
            f"DELETE FROM places WHERE place_id IN ({placeholders})",
            tuple(junk_ids),
        )

    return len(junk_ids)


# ═══════════════════════════════════════════════════════════════════
# PHASE 1 & 2: Match external geocoded datasets to DB records
# ═══════════════════════════════════════════════════════════════════

def _clean_place_name_for_matching(name):
    """Extract a clean matchable name from verbose DB entries.
    
    e.g. '1 Arulmigu Aadhilakshmi Varagaperumal Temple, Maranthai'
    -> 'arulmigu aadhilakshmi varagaperumal temple maranthai'
    """
    # Remove leading serial numbers
    name = re.sub(r"^\d+\s+", "", name.strip())
    # Remove special chars except spaces and basic punctuation
    name = re.sub(r"[–—\-,\.\(\)]", " ", name)
    return _normalize(name)


def _match_and_update(source_df, source_label):
    """Match a DataFrame with lat/lon against DB records missing coordinates.

    Uses multiple matching strategies:
    1. Exact name + district match
    2. Cleaned name contains match (for partial name overlap)
    """
    missing = _db_places_missing_coords()
    if not missing:
        print(f"  [{source_label}] No records need coordinates — skipping.")
        return 0

    # Build lookup from source data
    coords_map = {}  # (normalized_name, normalized_district) -> (lat, lon)
    source_names = {}  # normalized_district -> [(cleaned_name, lat, lon)]
    records = source_df.to_dict("records")
    for rec in records:
        name = _normalize(rec.get("place_name"))
        district = _normalize(rec.get("district"))
        lat = rec.get("latitude")
        lon = rec.get("longitude")
        if not name or not district or lat is None or lon is None:
            continue
        try:
            lat, lon = float(lat), float(lon)
        except (TypeError, ValueError):
            continue
        if not _in_tamilnadu(lat, lon):
            continue
        coords_map[(name, district)] = (lat, lon)
        source_names.setdefault(district, []).append((name, lat, lon))

    print(f"  [{source_label}] {len(coords_map)} geocoded source records (in TN bounds).")

    matched = 0
    for place in missing:
        db_name = _normalize(place["place_name"])
        db_district = _normalize(place["district"])
        db_clean = _clean_place_name_for_matching(place["place_name"])

        # Strategy 1: exact match
        key = (db_name, db_district)
        if key in coords_map:
            lat, lon = coords_map[key]
            _update_coords(place["place_id"], lat, lon)
            matched += 1
            continue

        # Strategy 2: cleaned name match
        key_clean = (db_clean, db_district)
        if key_clean in coords_map:
            lat, lon = coords_map[key_clean]
            _update_coords(place["place_id"], lat, lon)
            matched += 1
            continue

        # Strategy 3: source name contained in DB name or vice versa
        candidates = source_names.get(db_district, [])
        for src_name, lat, lon in candidates:
            if src_name in db_clean or db_clean in src_name:
                _update_coords(place["place_id"], lat, lon)
                matched += 1
                break

    print(f"  [{source_label}] Matched and updated: {matched}")
    return matched


# ═══════════════════════════════════════════════════════════════════
# PHASE 3: Nominatim geocoding for remaining gaps
# ═══════════════════════════════════════════════════════════════════

def _extract_geocoding_query(place_name, district, city=None):
    """Build smart Nominatim query strings from verbose place names.
    
    Returns a list of queries to try (most specific first).
    """
    # Clean up the name
    clean = re.sub(r"^\d+\s+", "", place_name.strip())  # Remove leading numbers
    clean = re.sub(r"\s*→\s*$", "", clean)  # Remove trailing arrows

    queries = []

    # If name contains comma, last part is likely a location
    parts = [p.strip() for p in clean.split(",") if p.strip()]
    if len(parts) >= 2:
        # "Arulmigu X Temple, LocationName" -> try "X Temple, LocationName, District"
        queries.append(f"{clean}, {district}")
        # Also try just the location part
        queries.append(f"{parts[-1]}, {district}")

    if city:
        queries.append(f"{clean}, {city}, {district}")

    queries.append(f"{clean}, {district}")

    # For very long names, try just the core place type
    if len(clean) > 40:
        # Extract the location portion after the last comma
        if "," in clean:
            loc = clean.split(",")[-1].strip()
            queries.append(f"{loc}, {district}")

    return queries[:3]  # Max 3 attempts per place


# Places Nominatim could not place in their district are remembered, so a
# resumed or repeated run spends its 1 request/second budget on new places.
# Keyed by name + district (stable across --reset rebuilds, unlike place_id).
GEOCODE_MISSES_PATH = Path(__file__).resolve().parent.parent / "data" / "cache" / "geocode_misses.json"


def _load_misses():
    try:
        return set(json.loads(GEOCODE_MISSES_PATH.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        return set()


def _save_misses(misses):
    GEOCODE_MISSES_PATH.parent.mkdir(parents=True, exist_ok=True)
    GEOCODE_MISSES_PATH.write_text(json.dumps(sorted(misses)), encoding="utf-8")


def _nominatim_enrich(limit=500, progress_interval=25, retry_misses=False):
    """Geocode remaining NULL-coordinate places via Nominatim.

    Rate-limited to 1 request per 1.1 seconds (public Nominatim policy).
    Validates results are within Tamil Nadu bounds.
    """
    missing = _db_places_missing_coords()
    misses = set() if retry_misses else _load_misses()
    key = lambda place: f"{place['district']}|{place['place_name']}"
    skipped = sum(1 for place in missing if key(place) in misses)
    missing = [place for place in missing if key(place) not in misses]
    if skipped:
        print(f"  [Nominatim] Skipping {skipped} places that could not be located before (use --retry-misses).")
    if not missing:
        print("  [Nominatim] No records need coordinates — skipping.")
        return 0

    batch = missing[:limit]
    print(f"  [Nominatim] Attempting to geocode {len(batch)} of {len(missing)} remaining places...")

    resolved = 0
    api_calls = 0
    for i, place in enumerate(batch, 1):
        name = place["place_name"]
        district = place["district"]
        city = place.get("city_town") or ""

        queries = _extract_geocoding_query(name, district, city)

        result = None
        for q in queries:
            result = geocode_in_district(q, district)
            api_calls += 1
            time.sleep(1.1)  # rate limit
            if result and _in_tamilnadu(result[0], result[1]):
                break
            result = None

        if result:
            _update_coords(place["place_id"], result[0], result[1])
            resolved += 1
        else:
            misses.add(key(place))

        if i % progress_interval == 0:
            _save_misses(misses)  # progress survives an interrupted run
            print(f"    ... {i}/{len(batch)} processed, {resolved} resolved, {api_calls} API calls")

    _save_misses(misses)
    print(f"  [Nominatim] Resolved: {resolved} / {len(batch)} ({api_calls} API calls)")
    return resolved


# ═══════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Enrich existing tourism DB with coordinates from OSM, Wikidata, and Nominatim"
    )
    parser.add_argument(
        "--nominatim-limit", type=int, default=500,
        help="Max places to geocode via Nominatim (default: 500)",
    )
    parser.add_argument(
        "--skip-nominatim", action="store_true",
        help="Only run OSM + Wikidata matching; skip Nominatim geocoding",
    )
    parser.add_argument(
        "--skip-osm", action="store_true",
        help="Skip OSM phase",
    )
    parser.add_argument(
        "--skip-wikidata", action="store_true",
        help="Skip Wikidata phase",
    )
    parser.add_argument(
        "--skip-cleanup", action="store_true",
        help="Skip junk record cleanup",
    )
    parser.add_argument(
        "--retry-misses", action="store_true",
        help="Also retry places Nominatim could not locate on an earlier run",
    )
    parser.add_argument(
        "--nominatim-only", action="store_true",
        help="Only run Nominatim phase (skip OSM and Wikidata)",
    )
    args = parser.parse_args()

    if args.nominatim_only:
        args.skip_osm = True
        args.skip_wikidata = True

    initialize_database()
    apply_migrations()

    total_before = _count_with_coords()
    total_places_before = _total_places()
    print(f"\n{'='*60}")
    print(f"Coordinate Enrichment")
    print(f"{'='*60}")
    print(f"Total places in DB:       {total_places_before}")
    print(f"With coordinates (before): {total_before}")
    print(f"Missing coordinates:       {total_places_before - total_before}")
    print(f"{'='*60}\n")

    # ── Phase 0: Cleanup ─────────────────────────────────────────
    if not args.skip_cleanup:
        print("Phase 0: Cleaning up web scraping artifacts...")
        removed = cleanup_junk_records()
        print(f"  Removed {removed} junk records.")
    else:
        print("Phase 0: Cleanup — skipped.")

    total_matched = 0

    # ── Phase 1: OSM ─────────────────────────────────────────────
    if not args.skip_osm:
        print("\nPhase 1: OpenStreetMap coordinate matching...")
        try:
            osm_df = scrape_openstreetmap_tourism()
            print(f"  OSM returned {len(osm_df)} records.")
            total_matched += _match_and_update(osm_df, "OSM")
        except Exception as e:
            print(f"  [OSM] Error: {e}")
    else:
        print("\nPhase 1: OSM — skipped.")

    # ── Phase 2: Wikidata ────────────────────────────────────────
    if not args.skip_wikidata:
        print("\nPhase 2: Wikidata coordinate matching...")
        try:
            wiki_df = scrape_wikidata_tourism()
            print(f"  Wikidata returned {len(wiki_df)} records.")
            total_matched += _match_and_update(wiki_df, "Wikidata")
        except Exception as e:
            print(f"  [Wikidata] Error: {e}")
    else:
        print("\nPhase 2: Wikidata — skipped.")

    # ── Phase 3: Nominatim ───────────────────────────────────────
    if not args.skip_nominatim:
        print(f"\nPhase 3: Nominatim geocoding (limit={args.nominatim_limit})...")
        total_matched += _nominatim_enrich(limit=args.nominatim_limit, retry_misses=args.retry_misses)
    else:
        print("\nPhase 3: Nominatim — skipped.")

    # ── Summary ──────────────────────────────────────────────────
    total_after = _count_with_coords()
    total_places_after = _total_places()
    still_missing = total_places_after - total_after
    print(f"\n{'='*60}")
    print(f"ENRICHMENT COMPLETE")
    print(f"{'='*60}")
    print(f"Total places (after cleanup): {total_places_after}")
    print(f"Coordinates before:  {total_before}")
    print(f"Coordinates after:   {total_after}")
    print(f"Newly enriched:      {total_after - total_before}")
    print(f"Still missing:       {still_missing}")
    print(f"Coverage:            {total_after}/{total_places_after} ({100*total_after/max(total_places_after,1):.1f}%)")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
