import sqlite3

import pytest

from preprocessing.merging import is_spelling_duplicate
from tests.test_scrapers import _ingestor, temp_db  # noqa: F401 (pytest fixture)


def _p(name, lat=None, lon=None, precision=None, district="Chennai", merged=None):
    return {"place_name": name, "district": district, "latitude": lat, "longitude": lon,
            "location_precision": precision, "merged_names": merged}


@pytest.mark.parametrize("a, b", [
    (_p("MGM Dizzee World", 12.80, 80.24), _p("MGM Dizee World", 12.801, 80.241)),
    (_p("Alamparai Fort"), _p("Alambarai Fort")),
    (_p("Hogenakkal Waterfalls"), _p("Hogenakkal Water Falls")),
    (_p("Udayagiriswarar koil"), _p("Udayagiriswararkoil")),
    (_p("Brough Memorial Church"), _p("CSI Brough Memorial Church")),
    (_p("Kamuthi Kottai"), _p("Kamudi Kottai")),
    (_p("Kelavarapalli Dam"), _p("Kellavarapalli Dam Park")),
    (_p("Narasimmar Temple, Sholingur"), _p("Narasimmar Temple, Sholingar")),
    (_p("Kachaleeswarar Temple", 13.090, 80.290), _p("Arulmigu Katchaleeshwarar Temple, Parrys", 13.091, 80.288)),
    # Same deity under another name, village written inside the name.
    (_p("Maruthamalai Murugan Temple"), _p("Arulmigu Subramaniaswamy Temple, Maruthamalai", 11.05, 76.85)),
    (_p("Vallakottai Subramaniyaswami temple"), _p("Vallakottai Murugan Temple")),
    (_p("Aliyar Dam", 10.4719, 76.9772), _p("Aliyar Reservoir", 10.4723, 76.9772)),
    # Renamed park; large areas' mapped centres sit km apart.
    (_p("Indira Gandhi National Park", 10.3478, 77.0947), _p("Anamalai Tiger Reserve", 10.3827, 77.0769)),
])
def test_spelling_variants_are_duplicates(a, b):
    assert is_spelling_duplicate(a, b)


@pytest.mark.parametrize("a, b", [
    # Neighbouring temples whose deity names differ by one consonant.
    (_p("Arulmigu Valeeswarar Temple, Mylapore", 13.03, 80.27), _p("Arulmigu Malleeswarar Temple, Mylapore", 13.03, 80.27)),
    (_p("Kachaleeswarar Temple", 13.09, 80.29), _p("Arulmigu Kapaleeswarar Temple, Mylapore", 13.03, 80.27)),
    # Same deity, different villages.
    (_p("Arulmigu Dharmaraja Temple, Saidapet"), _p("Arulmigu Dharmaraja Temple, Sowcarpet")),
    # A town/area vs an attraction named after it, or a different kind of place.
    (_p("Pykara"), _p("Pykara Waterfalls")),
    (_p("Subramaniya Swamy Temple, Tiruchendur"), _p("Subramaniya Swamy Kovil Beach")),
    (_p("Viralimalai"), _p("Viralimalai Sanctuary")),
    (_p("Maruthamalai"), _p("Arulmigu Subramaniaswamy Temple, Maruthamalai")),  # the hill, not the temple
    (_p("Velliangiri Murugan Temple"), _p("Arulmigu Subramaniaswamy Temple, Maruthamalai")),
    (_p("Thirugnana Sambanthar Moorthy Temple, Town"), _p("Thirugnana Sambanthar Moorthy Madam, Town")),
    # Same name, far apart.
    (_p("Kamakshi Amman Temple", 12.84, 79.70), _p("Arulmigu Kamakshi Amman Temple, Mangadu", 13.03, 80.11)),
    # An entry that already absorbed one village's temple never takes another village's.
    (_p("Agastheeswarar Swamy temple", 8.70, 77.45, merged="Arulmigu Agastheeswarar Temple, Kallidaikurichi"),
     _p("Arulmigu Agastheeswarar Temple, Ambasamudram", 8.71, 77.46)),
])
def test_different_places_are_not_duplicates(a, b):
    assert not is_spelling_duplicate(a, b)


def _insert(ingest, name, lat=None, lon=None, district="Tirunelveli"):
    place_id, _ = ingest.upsert_place({"place_name": name, "district": district, "category_name": "Temple",
                                       "latitude": lat, "longitude": lon, "source_id": None, "sources": []})
    return place_id


def test_merge_keeps_best_entry_and_records_merged_names(temp_db):  # noqa: F811
    with _ingestor(temp_db) as ingest:
        keeper = _insert(ingest, "Manimuthar Falls", 8.62, 77.41)
        _insert(ingest, "Manimuthar Waterfalls")
        assert ingest.merge_spelling_duplicates() == 1
    row = sqlite3.connect(temp_db).execute("SELECT place_id, place_name, merged_names FROM places").fetchall()
    assert row == [(keeper, "Manimuthar Falls", "Manimuthar Waterfalls")]


def test_ambiguous_entry_without_village_is_left_alone(temp_db):  # noqa: F811
    with _ingestor(temp_db) as ingest:
        _insert(ingest, "Arulmigu Agastheeswarar Swamy temple", 8.703, 77.45)
        _insert(ingest, "Arulmigu Agastheeswarar Temple, Ambasamudram", 8.710, 77.46)
        _insert(ingest, "Arulmigu Agastheeswarar Temple, Kallidaikurichi", 8.690, 77.47)
        assert ingest.merge_spelling_duplicates() == 0
    assert sqlite3.connect(temp_db).execute("SELECT COUNT(*) FROM places").fetchone() == (3,)
