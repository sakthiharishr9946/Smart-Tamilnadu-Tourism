from services.itinerary.generator import generate_itinerary
from services.itinerary.route_optimizer import calculate_route_distance, optimize_route


def _place(name, lat, lon, minutes=60):
    return {"place_name": name, "latitude": lat, "longitude": lon, "avg_visit_duration": minutes}


def test_route_visits_nearest_place_next():
    chennai = _place("Marina Beach", 13.05, 80.28)
    madurai = _place("Meenakshi Temple", 9.92, 78.12)
    mahabalipuram = _place("Shore Temple", 12.62, 80.20)
    route = optimize_route([chennai, madurai, mahabalipuram])
    assert [p["place_name"] for p in route] == ["Marina Beach", "Shore Temple", "Meenakshi Temple"]


def test_route_distance_ignores_places_without_coordinates():
    places = [_place("A", 13.05, 80.28), {"place_name": "No location"}, _place("B", 12.62, 80.20)]
    assert calculate_route_distance(places[:1]) == 0.0
    assert calculate_route_distance([places[0], places[2]]) > 40


def test_multi_day_itinerary_spreads_places_across_days():
    places = [_place(f"Place {i}", 11.0, 78.0, minutes=180) for i in range(4)]
    itinerary = generate_itinerary(places, days=2, start_time="09:00", end_time="17:00")
    scheduled = [entry["place"]["place_name"] for day in itinerary for entry in day.get("schedule", [])]
    assert scheduled == [f"Place {i}" for i in range(4)]
    assert all(len(day.get("schedule", [])) <= 2 for day in itinerary)
