"""Repeatable tourism-data and status update orchestration.

``refresh_tourism_data`` runs every collector, merges what they found and
writes the result in a single transaction:

1. scrape each source in parallel (no database lock is held meanwhile);
2. merge records describing the same destination across sources;
3. resolve licence/author for Wikimedia Commons images;
4. upsert places, images, provenance, festivals and holidays atomically;
5. remove scraping artefacts left behind by older collector versions.

Every source reports its own status, row count, duration and warnings, so a
source that breaks shows up in the report instead of silently returning
nothing.
"""

import logging
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Callable, Optional

from database.connection import fetch_all
from database.ingest import Ingestor
from database.migrations import apply_migrations
from database.queries import execute_query
from preprocessing.merging import merge_place_records
from scrapers.festivals import combine_festivals
from scrapers.government import (
    ARCHAEOLOGY_MONUMENTS_URL, FOREST_ECOTOURISM_URL, HRCE_COMMON_COLLECTION_URL, TTDC_DESTINATIONS_URL,
    WETLANDS_RAMSAR_URL, scrape_district_government_tourism, scrape_forest_ecotourism, scrape_hrce_temples,
    scrape_tamilnadu_archaeology, scrape_tamilnadu_wetlands, scrape_ttdc_destinations,
)
from scrapers.holidays import collect_holiday_rows
from scrapers.http_client import short_error
from scrapers.images import commons_file_title, fetch_commons_metadata
from scrapers.opendata import OVERPASS_URL, WIKIDATA_URL, scrape_openstreetmap_tourism, scrape_wikidata_tourism
from scrapers.parsing import is_junk_place_name
from services.data_quality import resolve_district
from services.location.geocoding import reverse_geocode_place

logger = logging.getLogger(__name__)

# Nominatim's usage policy caps public requests at 1/second.
NOMINATIM_MIN_INTERVAL_SECONDS = 1.1


@dataclass(frozen=True)
class Source:
    key: str
    name: str
    url: str
    source_type: str
    scrape: Callable
    license: Optional[str] = None


# Ordered by authority: when sources disagree on a name, description or
# category, the earlier source wins. Coordinates always prefer OSM/Wikidata.
SOURCES = (
    Source("ttdc", "Tamil Nadu Tourism (TTDC) official destinations", TTDC_DESTINATIONS_URL,
           "government website", scrape_ttdc_destinations),
    Source("district_portals", "38 Tamil Nadu district administration tourism portals",
           "https://www.tn.gov.in/district", "government district tourism portals",
           scrape_district_government_tourism),
    Source("forest", "Tamil Nadu Forest Department eco-tourism sites", FOREST_ECOTOURISM_URL,
           "government department", scrape_forest_ecotourism),
    Source("wetlands", "Tamil Nadu State Wetlands Authority", WETLANDS_RAMSAR_URL,
           "government authority", scrape_tamilnadu_wetlands),
    Source("archaeology", "Tamil Nadu Department of Archaeology", ARCHAEOLOGY_MONUMENTS_URL,
           "government department", scrape_tamilnadu_archaeology),
    Source("wikidata", "Wikidata district-linked tourism data", WIKIDATA_URL,
           "open data", scrape_wikidata_tourism, "CC0 1.0"),
    Source("osm", "OpenStreetMap / Overpass district boundaries", OVERPASS_URL,
           "open data", scrape_openstreetmap_tourism, "ODbL 1.0"),
    Source("hrce", "Tamil Nadu HR&CE public temple material", HRCE_COMMON_COLLECTION_URL,
           "government department", scrape_hrce_temples),
)
SOURCE_KEYS = tuple(source.key for source in SOURCES)
HOLIDAY_SOURCE = ("Tamil Nadu public holiday calendar", "https://pypi.org/project/holidays/", "open data", "MIT")


def _clear_places(connection):
    # Place-dependent tables first, to respect foreign keys. Reference tables
    # (categories, sources) are retained.
    for table in ("place_features", "place_status", "images", "ratings", "crowd_data", "place_sources"):
        connection.execute(f"DELETE FROM {table}")
    connection.execute("UPDATE festivals SET associated_place_id = NULL")
    connection.execute("DELETE FROM places")
    connection.execute("DELETE FROM search_history")


def reset_tourism_places():
    """Clear collected tourism records immediately.

    Prefer ``refresh_tourism_data(reset=True)``, which clears the old records
    in the same transaction that writes the new ones, so an interrupted or
    failed rebuild never leaves the application without data.
    """
    apply_migrations()
    from database.connection import get_connection
    connection = get_connection()
    try:
        _clear_places(connection)
        connection.commit()
    finally:
        connection.close()
    return {"status": "reset", "districts": 38}


def _run_source(source, options=None):
    started = time.monotonic()
    logger.info("Collecting %s ...", source.name)
    try:
        frame = source.scrape(**(options or {}))
        warnings = list(frame.attrs.get("warnings", []))
        result = {"status": "partial" if warnings else "ok", "rows": len(frame), "warnings": warnings, "error": None}
    except Exception as error:  # a broken source must never stop the refresh
        logger.warning("%s failed: %s", source.name, short_error(error))
        frame, result = None, {"status": "failed", "rows": 0, "warnings": [], "error": short_error(error)}
    result["seconds"] = round(time.monotonic() - started, 1)
    logger.info("%s: %s, %d rows in %.0fs", source.name, result["status"], result["rows"], result["seconds"])
    return source, frame, result


def _enrich_commons_images(places):
    urls = {image["image_url"] for place in places for image in place["images"]
            if commons_file_title(image["image_url"])}
    if not urls:
        return 0
    metadata = fetch_commons_metadata(urls)
    for place in places:
        enriched = []
        for image in place["images"]:
            if commons_file_title(image["image_url"]):
                info = metadata.get(image["image_url"])
                if not info:  # file deleted from Commons, or metadata unavailable
                    continue
                image = {**image, "image_url": info["image_url"], "image_license": info["image_license"],
                         "image_author": info["image_author"]}
            enriched.append(image)
        place["images"] = enriched
    return len(metadata)


def _remove_junk_places(ingestor):
    rows = ingestor.connection.execute("SELECT place_id, place_name, district FROM places").fetchall()
    junk = [row[0] for row in rows if is_junk_place_name(row[1], row[2]) or not resolve_district(row[2])]
    return ingestor.remove_places(junk)


def _clean_value(value):
    return None if isinstance(value, float) and value != value else value


def refresh_tourism_data(sources=None, skip=(), max_workers=4, source_options=None, reset=False):
    """Collect from every public source and update the database.

    ``sources``/``skip`` take keys from ``SOURCE_KEYS`` to run a subset;
    ``source_options`` maps a source key to keyword arguments for its
    scraper (e.g. ``{"osm": {"time_budget": 600}}``). ``reset`` rebuilds the
    places from scratch, atomically, and only when at least one source
    succeeded.
    Returns a report; ``records_updated`` and ``source`` keep their meaning
    for existing callers.
    """
    apply_migrations()
    skip = set(skip or ())
    selected = [s for s in SOURCES if (not sources or s.key in sources) and s.key not in skip]
    started = time.monotonic()

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        options = source_options or {}
        outcomes = list(pool.map(lambda source: _run_source(source, options.get(source.key)), selected))

    report: dict = {"sources": {source.key: result for source, _, result in outcomes}}
    succeeded = [(source, frame) for source, frame, _ in outcomes if frame is not None and not frame.empty]
    total_seen = sum(result["rows"] for _, _, result in outcomes)

    holidays = collect_holiday_rows()
    district_festivals = [f for _, frame in succeeded for f in frame.attrs.get("festivals", [])]
    rank = {source.key: position for position, source in enumerate(SOURCES)}

    if reset and not succeeded:
        raise RuntimeError("Reset aborted: no source returned data, existing places were kept")

    with Ingestor() as ingestor:
        if reset:
            _clear_places(ingestor.connection)
        source_ids = {
            source.key: ingestor.source_id(source.name, source.url, source.source_type, source.license)
            for source, _ in succeeded
        }
        records = []
        for source, frame in succeeded:
            for record in frame.to_dict("records"):
                record = {key: _clean_value(value) for key, value in record.items()}
                record["source_rank"] = rank[source.key]
                record["source_id"] = source_ids[source.key]
                records.append(record)

        places = merge_place_records(records)
        images_resolved = _enrich_commons_images(places)
        for place in places:
            ingestor.upsert_place(place)

        holiday_source_id = ingestor.source_id(*HOLIDAY_SOURCE)
        ingestor.upsert_holidays(holidays, holiday_source_id)
        ingestor.replace_festivals(combine_festivals([], holidays), holiday_source_id)
        if "district_portals" in source_ids and district_festivals:
            ingestor.replace_festivals(combine_festivals(district_festivals), source_ids["district_portals"])

        removed = _remove_junk_places(ingestor)
        duplicates_merged = ingestor.merge_cross_district_duplicates()
        spelling_duplicates_merged = ingestor.merge_spelling_duplicates()
        ingestor.update_prominence()
        stats = dict(ingestor.stats)

    counts = fetch_all(
        """SELECT COUNT(*) AS places,
                  SUM(latitude IS NOT NULL AND longitude IS NOT NULL) AS with_coordinates,
                  COUNT(DISTINCT district) AS districts
           FROM places"""
    )[0]
    report.update({
        "records_seen": total_seen,
        "records_merged": len(places),
        "records_updated": stats["places_inserted"] + stats["places_updated"],
        **stats,
        "commons_images_resolved": images_resolved,
        "junk_places_removed": removed,
        "cross_district_duplicates_merged": duplicates_merged,
        "spelling_duplicates_merged": spelling_duplicates_merged,
        "places_total": counts["places"],
        "places_with_coordinates": counts["with_coordinates"] or 0,
        "districts_covered": counts["districts"],
        "source": ", ".join(source.name for source, _ in succeeded) or "none available",
        "seconds": round(time.monotonic() - started, 1),
    })
    return report


def backfill_missing_cities(limit=50):
    """Resolve a real city/district for places that have coordinates but no
    city on record, via reverse geocoding.

    Many sources (Forest Department listings, Wikidata) only publish a
    coordinate, not a structured address, which is why "City: Unknown" shows
    up for places that otherwise have a precise location. Capped to `limit`
    per call and rate-limited to Nominatim's 1 request/second policy, since
    this is a slow, best-effort enrichment step rather than something to run
    unbounded on every page load.
    """
    rows = fetch_all(
        """SELECT place_id, latitude, longitude, district FROM places
           WHERE latitude IS NOT NULL AND longitude IS NOT NULL
             AND (city_town IS NULL OR TRIM(city_town) = '')
           LIMIT ?""",
        (limit,),
    )

    resolved = 0

    for row in rows:
        result = reverse_geocode_place(row["latitude"], row["longitude"])
        time.sleep(NOMINATIM_MIN_INTERVAL_SECONDS)

        if not result:
            continue

        city = result.get("city")
        district = result.get("district") or row["district"]

        if not city:
            continue

        execute_query(
            "UPDATE places SET city_town=?, district=COALESCE(?, district), "
            "updated_at=CURRENT_TIMESTAMP WHERE place_id=?",
            (city, district, row["place_id"]),
        )
        resolved += 1

    return {"checked": len(rows), "resolved": resolved}
