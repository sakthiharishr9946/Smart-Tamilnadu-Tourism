"""Transactional writes for the data collection pipeline.

Everything a refresh writes goes through one connection and one
transaction, so a crash or a failing source never leaves the database
half-updated, and thousands of upserts take seconds instead of minutes.
"""

import sqlite3

from database.connection import get_connection
from services.data_quality import RELATED_DISTRICTS, name_key

# Same-named entries in a parent/split district further apart than this are
# different places (two "Pine Forest"s: Kodaikanal and Ooty).
SAME_PLACE_MAX_KM = 15.0

# Tables whose rows follow a place when duplicates are merged.
_PLACE_CHILD_TABLES = ("images", "ratings", "crowd_data", "place_status")


def _close_enough(lat1, lon1, lat2, lon2):
    """True when either location is unknown or the two are within SAME_PLACE_MAX_KM."""
    if None in (lat1, lon1, lat2, lon2):
        return True
    from services.nearby.distance import calculate_distance
    return calculate_distance(lat1, lon1, lat2, lon2) <= SAME_PLACE_MAX_KM


_OPTIONAL_PLACE_FIELDS = ("city_town", "subcategory", "description", "latitude", "longitude", "address",
                          "wikidata_id", "osm_id", "source_url")


class Ingestor:
    """Context manager wrapping a refresh's database writes."""

    def __init__(self, connection=None):
        self.connection = connection or get_connection()
        self._categories = {}
        self.stats = {"places_inserted": 0, "places_updated": 0, "images_written": 0,
                      "festivals_written": 0, "holidays_written": 0}

    def __enter__(self):
        self.connection.execute("PRAGMA foreign_keys = ON")
        self.connection.execute("BEGIN")
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc_type is None:
            self.connection.commit()
        else:
            self.connection.rollback()
        self.connection.close()
        return False

    # -- reference data -------------------------------------------------
    def source_id(self, name, url, source_type, license_name=None, notes=None):
        row = self.connection.execute(
            "SELECT source_id FROM sources WHERE source_name = ? LIMIT 1", (name,)
        ).fetchone()
        if row:
            self.connection.execute(
                """UPDATE sources SET source_url = ?, source_type = ?, license = COALESCE(?, license),
                   notes = COALESCE(?, notes), collection_method = 'automated update',
                   last_checked = CURRENT_TIMESTAMP WHERE source_id = ?""",
                (url, source_type, license_name, notes, row[0]),
            )
            return row[0]
        cursor = self.connection.execute(
            """INSERT INTO sources (source_name, source_url, source_type, license, collection_method, last_checked, notes)
               VALUES (?, ?, ?, ?, 'automated update', CURRENT_TIMESTAMP, ?)""",
            (name, url, source_type, license_name, notes),
        )
        return cursor.lastrowid

    def category_id(self, category_name):
        if category_name not in self._categories:
            row = self.connection.execute(
                "SELECT category_id FROM categories WHERE category_name = ?", (category_name,)
            ).fetchone()
            if row:
                self._categories[category_name] = row[0]
            else:
                from config.categories import get_category_description
                cursor = self.connection.execute(
                    "INSERT INTO categories (category_name, description) VALUES (?, ?)",
                    (category_name, get_category_description(category_name) or "Collected tourism category"),
                )
                self._categories[category_name] = cursor.lastrowid
        return self._categories[category_name]

    # -- places -----------------------------------------------------------
    def _find_place(self, place):
        for column in ("wikidata_id", "osm_id"):
            if place.get(column):
                row = self.connection.execute(
                    f"SELECT place_id FROM places WHERE {column} = ? LIMIT 1", (place[column],)
                ).fetchone()
                if row:
                    return row[0]
        row = self.connection.execute(
            "SELECT place_id FROM places WHERE district = ? AND name_key = ? LIMIT 1",
            (place["district"], place["name_key"]),
        ).fetchone()
        if row:
            return row[0]
        # Same name under the district this one was split from/into
        # ("Yelagiri Hills": Vellore / Tirupathur) - the same place when
        # unambiguous and not far apart.
        related = RELATED_DISTRICTS.get(place["district"], [])
        if not related:
            return None
        rows = self.connection.execute(
            f"""SELECT place_id, district, latitude, longitude FROM places
                WHERE name_key = ? AND district IN ({",".join("?" * len(related))})""",
            (place["name_key"], *related),
        ).fetchall()
        matches = [r for r in rows if _close_enough(place.get("latitude"), place.get("longitude"), r[2], r[3])]
        if len(matches) == 1:
            place["district"] = matches[0][1]  # keep the district already on record
            return matches[0][0]
        return None

    def upsert_place(self, place):
        """Insert or refresh a merged place; returns (place_id, inserted)."""
        place = dict(place)
        place.setdefault("name_key", name_key(place["place_name"]))
        place["city_town"] = place.get("city") or place.get("city_town")
        values = {field: place.get(field) for field in _OPTIONAL_PLACE_FIELDS}
        category_id = self.category_id(place.get("category_name") or "Cultural")
        relevance = place.get("tourism_relevance") or 0
        existing = self._find_place(place)
        if existing:
            # COALESCE keeps what we already know when this run lacks a field.
            self.connection.execute(
                f"""UPDATE places SET place_name = ?, district = ?, category_id = ?, name_key = ?,
                    tourism_relevance = MAX(COALESCE(tourism_relevance, 0), ?), source_id = ?,
                    {", ".join(f"{field} = COALESCE(?, {field})" for field in _OPTIONAL_PLACE_FIELDS)},
                    location_precision = CASE WHEN ? IS NOT NULL THEN NULL ELSE location_precision END,
                    updated_at = CURRENT_TIMESTAMP
                    WHERE place_id = ?""",
                (place["place_name"], place["district"], category_id, place["name_key"], relevance,
                 place.get("source_id"), *values.values(), values["latitude"], existing),
            )
            place_id, inserted = existing, False
            self.stats["places_updated"] += 1
        else:
            columns = ["place_name", "district", "state", "category_id", "name_key", "tourism_relevance",
                       "source_id", *_OPTIONAL_PLACE_FIELDS]
            cursor = self.connection.execute(
                f"INSERT INTO places ({', '.join(columns)}) VALUES ({', '.join('?' * len(columns))})",
                (place["place_name"], place["district"], "Tamil Nadu", category_id, place["name_key"],
                 relevance, place.get("source_id"), *values.values()),
            )
            place_id, inserted = cursor.lastrowid, True
            self.stats["places_inserted"] += 1

        for source_id, source_url in place.get("sources") or []:
            if source_id is None:
                continue
            self.connection.execute(
                """INSERT INTO place_sources (place_id, source_id, source_url) VALUES (?, ?, ?)
                   ON CONFLICT(place_id, source_id, source_url) DO UPDATE SET last_seen = CURRENT_TIMESTAMP""",
                (place_id, source_id, source_url or ""),
            )
        self._write_images(place_id, place.get("images") or [])
        return place_id, inserted

    def _write_images(self, place_id, images):
        if not images:
            return
        has_primary = self.connection.execute(
            "SELECT 1 FROM images WHERE place_id = ? AND is_primary = 1 LIMIT 1", (place_id,)
        ).fetchone()
        for position, image in enumerate(images):
            try:
                cursor = self.connection.execute(
                    """INSERT INTO images (place_id, image_url, image_source, image_license, image_author, is_primary, source_id)
                       VALUES (?, ?, ?, ?, ?, ?, ?)
                       ON CONFLICT(place_id, image_url) DO UPDATE SET
                         image_source = excluded.image_source,
                         image_license = COALESCE(excluded.image_license, image_license),
                         image_author = COALESCE(excluded.image_author, image_author)""",
                    (place_id, image["image_url"], image.get("image_source"), image.get("image_license"),
                     image.get("image_author"), 1 if (position == 0 and not has_primary) else 0, image.get("source_id")),
                )
                self.stats["images_written"] += cursor.rowcount
            except sqlite3.IntegrityError:
                continue

    def merge_cross_district_duplicates(self):
        """Merge one place listed under a parent and a split district.

        The survivor is the entry with exact coordinates (else any
        coordinates, else the more prominent one); it keeps its district and
        gains the other's sources, photos, ratings and any fields it lacks.
        Returns the number of entries merged away.
        """
        merged = 0
        rows = self.connection.execute(
            """SELECT place_id, district, name_key, latitude, longitude, location_precision,
                      COALESCE(popularity_score, 0)
               FROM places WHERE name_key IS NOT NULL AND name_key != ''"""
        ).fetchall()
        by_key = {}
        for row in rows:
            by_key.setdefault(row[2], []).append(row)
        for group in by_key.values():
            if len(group) < 2:
                continue
            rank = lambda r: (r[3] is not None and r[5] is None, r[3] is not None, r[6])  # noqa: E731
            group = sorted(group, key=rank, reverse=True)
            keeper = group[0]
            for other in group[1:]:
                if other[1] not in RELATED_DISTRICTS.get(keeper[1], []):
                    continue
                # Approximate (village-centre) coordinates do not count as evidence of a different place.
                other_lat, other_lon = (None, None) if other[5] == "locality" else (other[3], other[4])
                if not _close_enough(keeper[3], keeper[4], other_lat, other_lon):
                    continue
                self._absorb_place(keeper[0], other[0])
                merged += 1
        return merged

    def find_spelling_duplicates(self):
        """Groups of place ids in one district that are the same place spelt
        differently ("MGM Dizzee World" / "MGM Dizee World"), best entry first.

        A place joins a group only when it matches every member (so two
        temples in different villages never merge through a third entry
        with no village in its name).
        """
        from preprocessing.merging import _name_parts, _same_locality, is_spelling_duplicate, place_localities
        rows = self.connection.execute(
            """SELECT p.place_id, p.place_name, p.district, p.latitude, p.longitude, p.location_precision,
                      p.merged_names, COALESCE(p.popularity_score, 0),
                      (SELECT COUNT(*) FROM place_sources s WHERE s.place_id = p.place_id)
               FROM places p"""
        ).fetchall()
        columns = ("place_id", "place_name", "district", "latitude", "longitude", "location_precision",
                   "merged_names", "popularity", "source_count")
        # Best entry first: exact coordinates, then more sources, then prominence.
        places = sorted((dict(zip(columns, row)) for row in rows),
                        key=lambda p: (p["latitude"] is None, p["location_precision"] == "locality",
                                       -p["source_count"], -p["popularity"], p["place_id"]))
        buckets = {}
        for place in places:
            key = _name_parts(place["place_name"], place["district"])[0]
            buckets.setdefault((place["district"], key[:1]), []).append(place)
        groups = []
        for members in buckets.values():
            # An entry naming no village that matches temples in two
            # different villages ("Agastheeswarar Temple" vs "..., Ambasamudram"
            # and "..., Kallidaikurichi") cannot be told apart: leave it alone.
            ambiguous = set()
            for place in members:
                if place_localities(place):
                    continue
                villages = [place_localities(other) for other in members
                            if other is not place and place_localities(other) and is_spelling_duplicate(place, other)]
                flat = [v for group in villages for v in group]
                if any(not _same_locality(x, y) for x in flat for y in flat):
                    ambiguous.add(place["place_id"])
            members = [p for p in members if p["place_id"] not in ambiguous]
            clusters = []
            for place in members:
                for cluster in clusters:
                    if all(is_spelling_duplicate(place, other) for other in cluster):
                        cluster.append(place)
                        break
                else:
                    clusters.append([place])
            groups += [[p["place_id"] for p in cluster] for cluster in clusters if len(cluster) > 1]
        return groups

    def merge_spelling_duplicates(self):
        """Merge every spelling-variant group into its best entry; returns how many entries were merged away."""
        merged = 0
        # A merged entry can match one more variant it did not match before
        # ("Gandhi Museum" + "Gandhi Memorial Museum", then "Gandhi Memorial").
        for _ in range(3):
            groups = self.find_spelling_duplicates()
            if not groups:
                break
            for keeper, *others in groups:
                for other in others:
                    self._absorb_place(keeper, other)
                    merged += 1
        return merged

    def _absorb_place(self, keeper_id, other_id):
        db = self.connection
        # Remember what was merged in: its village counts as this place's own
        # in later duplicate checks, so one entry never absorbs two temples
        # from different villages over successive refreshes.
        db.execute(
            """UPDATE places SET merged_names = TRIM(
                   COALESCE(merged_names, '') || '|' ||
                   (SELECT place_name || COALESCE('|' || merged_names, '') FROM places WHERE place_id = :other), '|')
               WHERE place_id = :keeper""",
            {"keeper": keeper_id, "other": other_id},
        )
        fields = ("city_town", "subcategory", "address", "wikidata_id", "osm_id", "source_url")
        db.execute(
            f"""UPDATE places SET
                  {", ".join(f"{f} = COALESCE({f}, (SELECT {f} FROM places WHERE place_id = :other))" for f in fields)},
                  description = CASE
                      WHEN LENGTH(COALESCE(description, '')) >=
                           LENGTH(COALESCE((SELECT description FROM places WHERE place_id = :other), ''))
                      THEN description ELSE (SELECT description FROM places WHERE place_id = :other) END,
                  tourism_relevance = MAX(COALESCE(tourism_relevance, 0),
                      COALESCE((SELECT tourism_relevance FROM places WHERE place_id = :other), 0)),
                  updated_at = CURRENT_TIMESTAMP
                WHERE place_id = :keeper""",
            {"keeper": keeper_id, "other": other_id},
        )
        db.execute("""INSERT OR IGNORE INTO place_sources (place_id, source_id, source_url, last_seen)
                      SELECT ?, source_id, source_url, last_seen FROM place_sources WHERE place_id = ?""",
                   (keeper_id, other_id))
        db.execute("DELETE FROM place_sources WHERE place_id = ?", (other_id,))
        for table in _PLACE_CHILD_TABLES:
            if table == "images":
                # unique (place_id, image_url): keep the keeper's copy of a shared photo
                db.execute("""DELETE FROM images WHERE place_id = ? AND image_url IN
                              (SELECT image_url FROM images WHERE place_id = ?)""", (other_id, keeper_id))
                db.execute("UPDATE images SET is_primary = 0 WHERE place_id = ? AND EXISTS "
                           "(SELECT 1 FROM images WHERE place_id = ? AND is_primary = 1)", (other_id, keeper_id))
            db.execute(f"UPDATE {table} SET place_id = ? WHERE place_id = ?", (keeper_id, other_id))
        db.execute("UPDATE festivals SET associated_place_id = ? WHERE associated_place_id = ?", (keeper_id, other_id))
        db.execute("DELETE FROM place_features WHERE place_id = ?", (other_id,))
        db.execute("DELETE FROM places WHERE place_id = ?", (other_id,))

    def remove_places(self, place_ids):
        place_ids = list(place_ids)
        for start in range(0, len(place_ids), 500):
            chunk = place_ids[start:start + 500]
            marks = ",".join("?" * len(chunk))
            for table in ("place_features", "place_status", "images", "ratings", "crowd_data", "place_sources"):
                self.connection.execute(f"DELETE FROM {table} WHERE place_id IN ({marks})", chunk)
            self.connection.execute(f"UPDATE festivals SET associated_place_id = NULL WHERE associated_place_id IN ({marks})", chunk)
            self.connection.execute(f"DELETE FROM places WHERE place_id IN ({marks})", chunk)
        return len(place_ids)

    def update_prominence(self):
        """Recompute ``popularity_score`` (0-100) for every place.

        No public source publishes visitor numbers or ratings, so prominence
        is derived from collection evidence: how authoritative the listing
        is, how many independent sources list the place, and whether it has
        a photo, coordinates, a Wikidata entry and a real description. The
        app's lists and recommendation scoring all rank on this column.
        """
        self.connection.execute(
            """UPDATE places SET popularity_score = ROUND(
                   35.0 * MIN(MAX(COALESCE(tourism_relevance, 0), 0), 1)
                 + 25.0 * MIN((SELECT COUNT(DISTINCT source_id) FROM place_sources s
                               WHERE s.place_id = places.place_id), 4) / 4.0
                 + 15.0 * EXISTS(SELECT 1 FROM images i WHERE i.place_id = places.place_id)
                 + 10.0 * (latitude IS NOT NULL AND longitude IS NOT NULL)
                 +  5.0 * (wikidata_id IS NOT NULL)
                 + 10.0 * (LENGTH(COALESCE(description, '')) >= 80), 1)"""
        )

    # -- calendar ---------------------------------------------------------
    def replace_festivals(self, festivals, source_id):
        """Festivals are re-published wholesale by each source."""
        self.connection.execute("DELETE FROM festivals WHERE source_id = ?", (source_id,))
        for festival in festivals:
            self.connection.execute(
                """INSERT INTO festivals (festival_name, district, start_date, end_date, month, festival_type,
                       importance, expected_tourism_impact, description, source_url, source_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (festival["festival_name"], festival.get("district"), festival.get("start_date"),
                 festival.get("end_date"), festival.get("month"), festival.get("festival_type"),
                 festival.get("importance") or "MEDIUM", festival.get("expected_tourism_impact"),
                 festival.get("description"), festival.get("source_url"), source_id),
            )
        self.stats["festivals_written"] += len(festivals)

    def upsert_holidays(self, holidays, source_id):
        for holiday in holidays:
            self.connection.execute(
                """INSERT INTO holidays (holiday_name, date, year, applicability, holiday_type, source_id)
                   VALUES (?, ?, ?, ?, ?, ?)
                   ON CONFLICT(holiday_name, date) DO UPDATE SET
                     applicability = excluded.applicability, holiday_type = excluded.holiday_type,
                     source_id = excluded.source_id""",
                (holiday["holiday_name"], holiday["date"], holiday["year"], holiday.get("applicability"),
                 holiday.get("holiday_type"), source_id),
            )
        self.stats["holidays_written"] += len(holidays)
