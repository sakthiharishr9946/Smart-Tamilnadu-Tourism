"""Locate places without coordinates using the free OpenStreetMap gazetteer.

    python scripts/locate_places.py            # download (cached) + match
    python scripts/locate_places.py --dry-run  # report matches, write nothing

For each place lacking coordinates it tries, in order:
  1. the place itself (temples matched among OSM places of worship near
     their village)                              -> exact
  2. the centre of the village / town it is in   -> "locality" (approximate)

The district downloads are cached for 30 days under data/cache/osm/gazetteer,
so re-runs take seconds. Only latitude, longitude and location_precision are
written, and only for places that had no coordinates.
"""

import argparse
import re
import sys
import time

sys.path.insert(0, ".")

from database.connection import get_connection  # noqa: E402
from database.migrations import apply_migrations  # noqa: E402
from scrapers.geonames import load_geonames_rows  # noqa: E402
from scrapers.osm_gazetteer import load_gazetteers  # noqa: E402
from scrapers.parsing import valid_tn_coordinates  # noqa: E402
from services.data_quality import RELATED_DISTRICTS  # noqa: E402

_TEMPLE_RE = re.compile(r"\b(temple|kovil|koil|thirukoil|amman|perumal|easwarar|eswarar|swamy|mutt)\b", re.I)


def _missing(connection):
    rows = connection.execute(
        """SELECT p.place_id, p.place_name, p.district, p.city_town, c.category_name
           FROM places p LEFT JOIN categories c ON c.category_id = p.category_id
           WHERE p.latitude IS NULL OR p.longitude IS NULL
           ORDER BY p.district, p.popularity_score DESC"""
    ).fetchall()
    return [dict(zip(("place_id", "place_name", "district", "city_town", "category_name"), row)) for row in rows]


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true", help="show what would be matched, write nothing")
    parser.add_argument("--district", action="append", help="only these districts (repeatable)")
    parser.add_argument("--osm-download", action="store_true",
                        help="also download OSM villages/temples per district (slow when Overpass is busy); "
                             "by default only OSM data already cached is used")
    args = parser.parse_args()

    apply_migrations()
    connection = get_connection()
    missing = _missing(connection)
    if args.district:
        missing = [p for p in missing if p["district"] in args.district]
    districts = sorted({p["district"] for p in missing if p["district"]})
    total = connection.execute("SELECT COUNT(*) FROM places").fetchone()[0]
    located_before = total - len(_missing(connection))
    print(f"{len(missing)} places without coordinates across {len(districts)} districts.")
    print("Loading gazetteers: GeoNames (one 16 MB download, cached) + OpenStreetMap...")

    started = time.monotonic()
    wanted = sorted(set(districts) | {n for d in districts for n in RELATED_DISTRICTS.get(d, ())})
    gazetteers = load_gazetteers(wanted, extra_rows=load_geonames_rows(), download=args.osm_download)
    print(f"Gazetteer ready for {len(gazetteers)}/{len(wanted)} districts in {time.monotonic() - started:.0f}s.\n")

    updates, counts = [], {"exact": 0, "locality": 0, "not found": 0, "no gazetteer": 0, "neighbour": 0}
    for place in missing:
        gazetteer = gazetteers.get(place["district"])
        if gazetteer is None:
            counts["no gazetteer"] += 1
            continue
        is_temple = place["category_name"] == "Temple" or bool(_TEMPLE_RE.search(place["place_name"]))
        found = gazetteer.locate(place["place_name"], place["city_town"], is_temple=is_temple,
                                 district=place["district"])
        if not found:
            # Listed under the district it was split from (or into): look
            # there too, exact village names only.
            for neighbour in RELATED_DISTRICTS.get(place["district"], ()):
                if neighbour in gazetteers:
                    found = gazetteers[neighbour].locate(place["place_name"], place["city_town"],
                                                         is_temple=is_temple, district=neighbour, exact_only=True)
                    if found:
                        counts["neighbour"] += 1
                        break
        latitude, longitude = valid_tn_coordinates(*found[:2]) if found else (None, None)
        if latitude is None:
            counts["not found"] += 1
            continue
        precision = found[2]
        counts[precision] += 1
        updates.append((latitude, longitude, None if precision == "exact" else precision, place["place_id"]))
        if args.dry_run and len(updates) <= 40:
            print(f"  [{precision:8}] {place['place_name'][:60]:60} -> {found[3]}")

    if not args.dry_run and updates:
        with connection:
            connection.executemany(
                """UPDATE places SET latitude = ?, longitude = ?, location_precision = ?,
                   updated_at = CURRENT_TIMESTAMP
                   WHERE place_id = ? AND (latitude IS NULL OR longitude IS NULL)""",
                updates,
            )
    located_after = located_before + (0 if args.dry_run else len(updates))
    connection.close()

    print("=" * 60)
    print(f"Matched exactly (the place itself): {counts['exact']}")
    print(f"Placed at village/town centre:      {counts['locality']}")
    print(f"  (found via the parent/split district: {counts['neighbour']})")
    print(f"Not found (GeoNames / OSM):         {counts['not found']}")
    if counts["no gazetteer"]:
        print(f"District download failed (re-run):  {counts['no gazetteer']}")
    print(f"Coverage: {located_before}/{total} -> {located_after}/{total} "
          f"({100 * located_after / max(total, 1):.1f}%){'  [dry run]' if args.dry_run else ''}")


if __name__ == "__main__":
    main()
