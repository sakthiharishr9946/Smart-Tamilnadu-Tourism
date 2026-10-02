"""Fill weak descriptions and missing photos from free Wikipedia / Commons.

    python scripts/enrich_wikipedia.py            # update the database
    python scripts/enrich_wikipedia.py --dry-run  # report, write nothing

Only places linked to an article through their own identifiers (OSM
``wikipedia`` tag or Wikidata enwiki sitelink) are considered, and an
article is used only when its title matches the place or its coordinates
are within 2 km. Descriptions are replaced only when missing or shorter
than 80 characters; photos are added only for places without one, and only
freely licensed Wikimedia Commons files (with licence and author recorded).
"""

import argparse
import glob
import json
import sys

sys.path.insert(0, ".")

from database.ingest import Ingestor  # noqa: E402
from database.migrations import apply_migrations  # noqa: E402
from scrapers.images import fetch_commons_metadata  # noqa: E402
from scrapers.osm_gazetteer import haversine_km  # noqa: E402
from scrapers.opendata import OSM_CACHE_DIR  # noqa: E402
from scrapers.parsing import truncate  # noqa: E402
from scrapers.wikipedia import (  # noqa: E402
    article_matches_place,
    fetch_summaries,
    osm_wikipedia_title,
    wikidata_enwiki_titles,
)

MIN_DESCRIPTION_LENGTH = 80
WIKIPEDIA_SOURCE = ("English Wikipedia (article summaries)", "https://en.wikipedia.org/", "encyclopedia",
                    "CC BY-SA 4.0")


def _osm_titles():
    """{"node/123": "Title"} from the cached OSM district payloads."""
    titles = {}
    for path in glob.glob(str(OSM_CACHE_DIR / "[0-9]*.json")):
        try:
            elements = json.load(open(path, encoding="utf-8")).get("elements", [])
        except (OSError, ValueError):
            continue
        for element in elements:
            title = osm_wikipedia_title(element.get("tags"))
            if title:
                titles[f"{element.get('type')}/{element.get('id')}"] = title
    return titles


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    apply_migrations()

    with Ingestor() as ingest:
        db = ingest.connection
        rows = db.execute(
            """SELECT p.place_id, p.place_name, p.description, p.latitude, p.longitude, p.osm_id, p.wikidata_id,
                      EXISTS (SELECT 1 FROM images i WHERE i.place_id = p.place_id) AS has_image
               FROM places p
               WHERE (p.osm_id IS NOT NULL OR p.wikidata_id IS NOT NULL)
                 AND (p.description IS NULL OR LENGTH(p.description) < ?
                      OR NOT EXISTS (SELECT 1 FROM images i WHERE i.place_id = p.place_id))""",
            (MIN_DESCRIPTION_LENGTH,),
        ).fetchall()
        columns = ("place_id", "place_name", "description", "latitude", "longitude", "osm_id", "wikidata_id",
                   "has_image")
        places = [dict(zip(columns, row)) for row in rows]
        print(f"{len(places)} places linked to OSM/Wikidata need a description or photo.")

        osm_titles = _osm_titles()
        wikidata_titles = wikidata_enwiki_titles([p["wikidata_id"] for p in places])
        for place in places:
            place["title"] = osm_titles.get(place["osm_id"] or "") or wikidata_titles.get(place["wikidata_id"] or "")
        linked = [p for p in places if p["title"]]
        print(f"{len(linked)} of them have an English Wikipedia article. Fetching summaries...")

        summaries = fetch_summaries([p["title"] for p in linked])
        accepted = []
        rejected = 0
        for place in linked:
            summary = summaries.get(place["title"])
            if not summary:
                continue
            distance = None
            if None not in (place["latitude"], place["longitude"], summary["latitude"], summary["longitude"]):
                distance = haversine_km(place["latitude"], place["longitude"],
                                        summary["latitude"], summary["longitude"])
            if not article_matches_place(summary, place, distance):
                rejected += 1
                continue
            accepted.append((place, summary))

        image_meta = fetch_commons_metadata(
            [f"https://commons.wikimedia.org/wiki/Special:FilePath/{s['image_file']}"
             for p, s in accepted if s["image_file"] and not p["has_image"]]
        )

        source_id = ingest.source_id(*WIKIPEDIA_SOURCE[:3], license_name=WIKIPEDIA_SOURCE[3],
                                     notes="Intro summaries of articles linked from OSM/Wikidata")
        descriptions = photos = 0
        for place, summary in accepted:
            current = place["description"] or ""
            if len(current) < MIN_DESCRIPTION_LENGTH and len(summary["extract"]) >= MIN_DESCRIPTION_LENGTH:
                descriptions += 1
                if args.dry_run and descriptions <= 8:
                    print(f"  {place['place_name'][:40]:40} <- {summary['extract'][:90]}...")
                if not args.dry_run:
                    db.execute("UPDATE places SET description = ?, updated_at = CURRENT_TIMESTAMP WHERE place_id = ?",
                               (truncate(summary["extract"]), place["place_id"]))
            meta = image_meta.get(f"https://commons.wikimedia.org/wiki/Special:FilePath/{summary['image_file']}")
            if meta and not place["has_image"]:
                photos += 1
                if not args.dry_run:
                    ingest._write_images(place["place_id"], [{
                        "image_url": meta["image_url"], "image_source": "Wikimedia Commons (via Wikipedia)",
                        "image_license": meta["image_license"], "image_author": meta["image_author"],
                        "source_id": source_id,
                    }])
            if not args.dry_run:
                db.execute(
                    """INSERT INTO place_sources (place_id, source_id, source_url) VALUES (?, ?, ?)
                       ON CONFLICT(place_id, source_id, source_url) DO UPDATE SET last_seen = CURRENT_TIMESTAMP""",
                    (place["place_id"], source_id, summary["url"]),
                )
        if args.dry_run:
            db.rollback()
            db.execute("BEGIN")
        else:
            ingest.update_prominence()

    print("=" * 60)
    print(f"Articles about a different subject (skipped): {rejected}")
    print(f"Descriptions filled from Wikipedia:          {descriptions}")
    print(f"Photos added from Wikimedia Commons:         {photos}")
    if args.dry_run:
        print("[dry run - nothing written]")


if __name__ == "__main__":
    main()
