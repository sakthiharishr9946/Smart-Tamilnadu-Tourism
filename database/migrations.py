"""Small, repeatable database upgrades for the tourism application."""

from database.connection import get_connection


STATUS_SCHEMA = """
CREATE TABLE IF NOT EXISTS place_status (
    status_id INTEGER PRIMARY KEY AUTOINCREMENT,
    place_id INTEGER NOT NULL,
    status TEXT NOT NULL,
    suitability_score REAL DEFAULT 1.0,
    details TEXT,
    source_id INTEGER,
    source_url TEXT,
    checked_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at TEXT,
    FOREIGN KEY (place_id) REFERENCES places(place_id) ON DELETE CASCADE,
    FOREIGN KEY (source_id) REFERENCES sources(source_id) ON DELETE SET NULL,
    CHECK (suitability_score >= 0 AND suitability_score <= 1)
);
CREATE INDEX IF NOT EXISTS idx_place_status_latest
ON place_status(place_id, checked_at DESC);
"""


# Columns used by the multi-source collector: a normalised name key for
# cross-source matching, stable external identifiers, and provenance.
PLACE_COLUMNS_TO_ADD = {
    "name_key": "TEXT",
    "source_url": "TEXT",
    "wikidata_id": "TEXT",
    "osm_id": "TEXT",
    # NULL = coordinates of the place itself; "locality" = centre of the
    # village/town it stands in (approximate, shown as such in the UI).
    "location_precision": "TEXT",
    # "|"-separated names of entries merged into this place (duplicate clean-up).
    "merged_names": "TEXT",
}

COLLECTOR_SCHEMA = """
CREATE INDEX IF NOT EXISTS idx_places_name_key ON places(district, name_key);
CREATE INDEX IF NOT EXISTS idx_places_wikidata ON places(wikidata_id);
CREATE INDEX IF NOT EXISTS idx_places_osm ON places(osm_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_images_place_url ON images(place_id, image_url);
CREATE INDEX IF NOT EXISTS idx_festivals_source ON festivals(source_id);
CREATE TABLE IF NOT EXISTS place_sources (
    place_id INTEGER NOT NULL,
    source_id INTEGER NOT NULL,
    source_url TEXT NOT NULL DEFAULT '',
    last_seen TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (place_id, source_id, source_url),
    FOREIGN KEY (place_id) REFERENCES places(place_id) ON DELETE CASCADE,
    FOREIGN KEY (source_id) REFERENCES sources(source_id) ON DELETE CASCADE
);
"""


FESTIVAL_COLUMNS_TO_ADD = {
    "description": "TEXT",
    "source_url": "TEXT",
}


def _add_missing_columns(connection, table, columns):
    existing = {row[1] for row in connection.execute(f"PRAGMA table_info({table})")}
    added = []
    for column, column_type in columns.items():
        if column not in existing:
            connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {column_type}")
            added.append(column)
    return added


def _add_missing_place_columns(connection):
    added = _add_missing_columns(connection, "places", PLACE_COLUMNS_TO_ADD)
    if "name_key" in added:
        from services.data_quality import name_key
        rows = connection.execute("SELECT place_id, place_name FROM places").fetchall()
        connection.executemany(
            "UPDATE places SET name_key = ? WHERE place_id = ?",
            [(name_key(row[1]), row[0]) for row in rows],
        )


def _remove_duplicate_images(connection):
    # Required before the (place_id, image_url) unique index can be created.
    connection.execute(
        """DELETE FROM images WHERE image_id NOT IN (
               SELECT MIN(image_id) FROM images GROUP BY place_id, image_url)"""
    )


def apply_migrations(connection=None):
    """Apply idempotent additions without replacing existing tourism data.

    Pass ``connection`` to migrate a specific database (tests use this);
    otherwise the application database is used.
    """
    owns_connection = connection is None
    connection = connection or get_connection()
    try:
        connection.executescript(STATUS_SCHEMA)
        _add_missing_place_columns(connection)
        _add_missing_columns(connection, "festivals", FESTIVAL_COLUMNS_TO_ADD)
        _add_missing_columns(connection, "ratings", {"review": "TEXT"})
        _remove_duplicate_images(connection)
        connection.executescript(COLLECTOR_SCHEMA)
        connection.commit()
    finally:
        if owns_connection:
            connection.close()
