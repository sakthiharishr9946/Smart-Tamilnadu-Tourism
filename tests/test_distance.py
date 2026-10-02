from services.nearby.distance import (
    calculate_distance,
    add_distance_to_places,
    filter_by_distance,
    sort_by_distance,
)


def test_same_location_distance():
    distance = calculate_distance(
        11.0168,
        76.9558,
        11.0168,
        76.9558,
    )

    assert distance == 0


def test_distance_is_positive():
    distance = calculate_distance(
        11.0168,
        76.9558,
        13.0827,
        80.2707,
    )

    assert distance > 0


def test_invalid_coordinates():
    distance = calculate_distance(
        "invalid",
        76.9558,
        11.0168,
        76.9558,
    )

    assert distance is None


def test_add_distance_to_places():
    places = [
        {
            "place_id": 1,
            "place_name": "Coimbatore",
            "latitude": 11.0168,
            "longitude": 76.9558,
        }
    ]

    result = add_distance_to_places(
        places,
        11.0168,
        76.9558,
    )

    assert len(result) == 1
    assert "distance_km" in result[0]
    assert result[0]["distance_km"] == 0


def test_filter_by_distance():
    places = [
        {"place_name": "Place A", "distance_km": 5},
        {"place_name": "Place B", "distance_km": 20},
        {"place_name": "Place C", "distance_km": 50},
    ]

    result = filter_by_distance(
        places,
        20,
    )

    assert len(result) == 2


def test_sort_by_distance():
    places = [
        {"place_name": "A", "distance_km": 30},
        {"place_name": "B", "distance_km": 10},
        {"place_name": "C", "distance_km": 20},
    ]

    result = sort_by_distance(places)

    assert result[0]["place_name"] == "B"
    assert result[1]["place_name"] == "C"
    assert result[2]["place_name"] == "A"

from services.nearby.distance import filter_by_distance


def test_filter_by_distance_strict_boundary():
    places = [
        {"place_id": 1, "distance_km": 49.999999},
        {"place_id": 2, "distance_km": 50.0},
        {"place_id": 3, "distance_km": 50.000001},
        {"place_id": 4, "distance_km": None},
    ]
    result = filter_by_distance(places, 50)
    assert [p["place_id"] for p in result] == [1, 2]
    assert all(float(p["distance_km"]) <= 50 for p in result)
