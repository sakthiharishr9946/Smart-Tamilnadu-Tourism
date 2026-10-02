from scrapers.osm_gazetteer import DistrictGazetteer, compact_elements, core_name_key, split_locality

ELEMENTS = [
    {"type": "node", "lat": 12.30, "lon": 79.30, "tags": {"place": "village", "name": "Vallandaramam"}},
    {"type": "node", "lat": 12.80, "lon": 79.10, "tags": {"place": "town", "name": "Arani"}},
    {"type": "way", "center": {"lat": 12.302, "lon": 79.305},
     "tags": {"amenity": "place_of_worship", "religion": "hindu", "name": "Porkodi Amman Kovil"}},
    {"type": "way", "center": {"lat": 12.79, "lon": 79.11},
     "tags": {"amenity": "place_of_worship", "name": "Subramanya Swamy Temple"}},
    # Two villages with the same name 40 km apart: ambiguous.
    {"type": "node", "lat": 12.10, "lon": 79.00, "tags": {"place": "hamlet", "name": "Palur"}},
    {"type": "node", "lat": 12.50, "lon": 79.40, "tags": {"place": "hamlet", "name": "Palur"}},
    {"type": "node", "lat": 12.6, "lon": 79.2, "tags": {"place": "village", "name": "கிராமம்"}},  # Tamil only
]


def _gazetteer():
    return DistrictGazetteer(compact_elements(ELEMENTS))


def test_compact_elements_keeps_latin_and_tamil_named_points():
    rows = compact_elements(ELEMENTS)
    assert len(rows) == 7
    assert {row["kind"] for row in rows} == {"settlement", "worship"}


def test_core_name_and_locality():
    assert core_name_key("Arulmigu Subramaniya Swamy Temple") == core_name_key("Sri Subramaniya Kovil")
    assert split_locality("Arulmigu X Temple, Perambur, Tiruvannamalai", district="Tiruvannamalai") == (
        "Arulmigu X Temple", ["Perambur", "Tiruvannamalai"])  # district name last
    assert split_locality("X Temple, Velapadi", "Vellore") == ("X Temple", ["Velapadi", "Vellore"])
    assert split_locality("X Temple", "Arani") == ("X Temple", ["Arani"])


def test_sound_alike_village_is_not_matched():
    assert _gazetteer().locate("Arulmigu Kali Temple, Valandaramam") is not None  # spelling variant
    assert _gazetteer().locate("Arulmigu Kali Temple, Kallandaramam") is None  # different first letter


def test_temple_matched_near_its_village():
    found = _gazetteer().locate("Arulmigu Porkodiamman Temple, Vallandaramam")
    assert found[2] == "exact" and found[:2] == (12.302, 79.305)


def test_falls_back_to_village_centre():
    found = _gazetteer().locate("Arulmigu Kaliamman Temple, Vallandaramam")
    assert found[2] == "locality" and found[:2] == (12.30, 79.30)


def test_spelling_variant_of_temple_matches():
    found = _gazetteer().locate("Arulmigu Subramaniya Swamy Temple, Arani")
    assert found[2] == "exact"


def test_ambiguous_village_is_not_guessed():
    assert _gazetteer().locate("Arulmigu Kali Temple, Palur") is None


def test_unknown_place_returns_none():
    assert _gazetteer().locate("Arulmigu Kali Temple, Nowhere") is None


def test_tamil_only_village_name_matches_latin_spelling():
    rows = compact_elements([{"type": "node", "lat": 12.9, "lon": 79.1,
                              "tags": {"place": "village", "name": "வேலப்பாடி"}}])
    found = DistrictGazetteer(rows).locate("Arulmigu Dharmaraja Temple, Velapadi")
    assert found[2] == "locality" and found[:2] == (12.9, 79.1)
