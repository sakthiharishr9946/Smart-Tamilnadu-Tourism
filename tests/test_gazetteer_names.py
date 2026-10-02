from scrapers.osm_gazetteer import DistrictGazetteer, name_localities

ROWS = [
    {"kind": "settlement", "rank": 3, "lat": 11.13, "lon": 79.85, "names": ["Poompuhar"]},
    {"kind": "settlement", "rank": 3, "lat": 10.07, "lon": 78.21, "names": ["Alagarkovil"]},
    {"kind": "settlement", "rank": 6, "lat": 12.50, "lon": 79.90, "names": ["Kailasanathar"]},
    {"kind": "settlement", "rank": 1, "lat": 8.08, "lon": 77.55, "names": ["Kanniyakumari"]},
]


def _gazetteer():
    return DistrictGazetteer(ROWS)


def test_name_localities():
    assert name_localities("Poompuhar Beach") == ["Poompuhar Beach", "Poompuhar"]
    assert name_localities("Kamarajar Manimandapam at Kanniyakumari")[0] == "Kanniyakumari"
    assert name_localities("Kailasanathar Temple", strip_features=False) == ["Kailasanathar Temple"]


def test_village_inside_destination_name():
    assert _gazetteer().locate("Poompuhar Beach", is_temple=False)[:3] == (11.13, 79.85, "locality")
    assert _gazetteer().locate("Alagar Kovil", is_temple=True)[:2] == (10.07, 78.21)
    assert _gazetteer().locate("Kamarajar Manimandapam at Kanniyakumari", is_temple=False)[:2] == (8.08, 77.55)


def test_temple_deity_name_is_not_taken_for_a_village():
    assert _gazetteer().locate("Arulmigu Kailasanathar Temple, Kovalam", is_temple=True) is None


def test_exact_only_rejects_spelling_variants():
    assert _gazetteer().locate("X Temple, Alagarkoil", is_temple=True, exact_only=True) is None
    assert _gazetteer().locate("X Temple, Alagarkoil", is_temple=True) is not None  # fuzzy allowed at home
