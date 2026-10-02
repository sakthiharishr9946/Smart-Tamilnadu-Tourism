import services.search.start_search as start_search_module

PLACES = [
    {"place_id": 1, "place_name": "Ooty Lake", "district": "Nilgiris", "category_name": "Nature",
     "latitude": 11.4064, "longitude": 76.6932},
    {"place_id": 2, "place_name": "Marina Beach", "district": "Chennai", "category_name": "Beach",
     "latitude": 13.0500, "longitude": 80.2824},
    {"place_id": 3, "place_name": "Unlocated Temple", "district": "Vellore", "category_name": "Temple",
     "latitude": None, "longitude": None},
]


def _patch(monkeypatch):
    monkeypatch.setattr(start_search_module, "get_all_places", lambda: PLACES)
    monkeypatch.setattr(start_search_module, "record_search_history", lambda *args: None)
    monkeypatch.setattr(start_search_module, "add_status_to_places", lambda places: places)


def test_nearby_search_finds_close_places(monkeypatch):
    _patch(monkeypatch)
    results, context = start_search_module.start_search(11.41, 76.70, min_results=1)
    assert [place["place_name"] for place in results] == ["Ooty Lake"]
    assert context["message"] == "Nearby destinations ranked for you."


def test_far_away_location_falls_back_to_closest(monkeypatch):
    _patch(monkeypatch)
    # Bengaluru: nothing within 100 km, so the closest places are returned.
    results, context = start_search_module.start_search(12.97, 77.59, min_results=2)
    names = [place["place_name"] for place in results]
    assert names and "Unlocated Temple" not in names
    assert "closest" in context["message"]
    assert context["radius_km"] > 100
