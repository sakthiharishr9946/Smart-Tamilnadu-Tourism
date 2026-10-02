from services.itinerary.generator import generate_itinerary


def test_end_time_limits_visits_and_lists_remaining():
    places = [
        {"place_name": "A", "avg_visit_duration": 120},
        {"place_name": "B", "avg_visit_duration": 120},
        {"place_name": "C", "avg_visit_duration": 120},
    ]
    result = generate_itinerary(places, days=1, start_time="09:00", end_time="13:30")
    assert [x["place"]["place_name"] for x in result[0]["schedule"]] == ["A", "B"]
    assert [x["place_name"] for x in result[-1]["remaining_places"]] == ["C"]
