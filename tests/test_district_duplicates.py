import sqlite3

from tests.test_scrapers import _ingestor, temp_db  # noqa: F401 (pytest fixture)


def _place(name, district, lat=None, lon=None, **extra):
    return {"place_name": name, "district": district, "category_name": "Hill", "latitude": lat,
            "longitude": lon, "source_id": None, "sources": [], **extra}


def test_old_district_listing_updates_the_existing_place(temp_db):  # noqa: F811
    with _ingestor(temp_db) as ingest:
        first, _ = ingest.upsert_place(_place("Yelagiri Hills", "Tirupathur", 12.58, 78.64))
        # A source still filing it under Vellore (the district it was split from).
        second, inserted = ingest.upsert_place(_place("Yelagiri Hills", "Vellore", description="Hill station"))
    assert second == first and not inserted
    row = sqlite3.connect(temp_db).execute("SELECT COUNT(*), district, description FROM places").fetchone()
    assert row == (1, "Tirupathur", "Hill station")


def test_same_name_far_apart_stays_separate(temp_db):  # noqa: F811
    with _ingestor(temp_db) as ingest:
        ingest.upsert_place(_place("Old Lighthouse", "Chennai", 13.04, 80.28))
        _, inserted = ingest.upsert_place(_place("Old Lighthouse", "Chengalpattu", 12.62, 80.19))  # ~47 km
    assert inserted


def test_unrelated_districts_never_merge(temp_db):  # noqa: F811
    with _ingestor(temp_db) as ingest:
        ingest.upsert_place(_place("Pine Forest", "Dindigul"))
        _, inserted = ingest.upsert_place(_place("Pine Forest", "Nilgiris"))
    assert inserted


def test_merge_existing_duplicates_keeps_exact_location(temp_db):  # noqa: F811
    connection = sqlite3.connect(temp_db)
    with _ingestor(temp_db) as ingest:
        exact, _ = ingest.upsert_place(_place("Covelong Beach", "Chengalpattu", 12.79, 80.25))
        source = ingest.source_id("Gov", "https://gov", "government")
        # Inserted directly: older data written before cross-district matching.
        cursor = ingest.connection.execute(
            "INSERT INTO places (place_name, district, category_id, name_key, latitude, longitude, location_precision, description)"
            " VALUES ('Covelong Beach', 'Chennai', ?, 'covelong beach', 12.80, 80.26, 'locality', 'Fishing village beach')",
            (ingest.category_id("Beach"),))
        approx = cursor.lastrowid
        ingest.connection.execute("INSERT INTO place_sources (place_id, source_id, source_url) VALUES (?, ?, 'u')",
                                  (approx, source))
        ingest.connection.execute("INSERT INTO ratings (place_id, rating, rating_count) VALUES (?, 5, 1)", (approx,))
        assert ingest.merge_cross_district_duplicates() == 1
    places = connection.execute("SELECT place_id, district, latitude, description FROM places").fetchall()
    assert places == [(exact, "Chengalpattu", 12.79, "Fishing village beach")]
    assert connection.execute("SELECT place_id FROM place_sources").fetchall() == [(exact,)]
    assert connection.execute("SELECT place_id FROM ratings").fetchall() == [(exact,)]
