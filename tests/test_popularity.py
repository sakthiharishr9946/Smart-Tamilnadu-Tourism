from services.recommendation.popularity import (
    calculate_popularity_score,
    add_popularity_score,
    add_popularity_to_places,
)


def test_popularity_score_range():
    score = calculate_popularity_score(
        rating=5,
        rating_count=1000,
        tourism_visitors=100000,
    )

    assert 0 <= score <= 100


def test_zero_popularity():
    score = calculate_popularity_score(
        rating=0,
        rating_count=0,
        tourism_visitors=0,
    )

    assert score == 0


def test_add_popularity_score():
    place = {
        "place_name": "Marina Beach",
        "rating": 4.5,
        "rating_count": 500,
        "tourism_visitors": 50000,
    }

    result = add_popularity_score(place)

    assert "popularity_score" in result
    assert result["popularity_score"] > 0


def test_add_popularity_to_places():
    places = [
        {
            "place_name": "A",
            "rating": 4,
            "rating_count": 100,
            "tourism_visitors": 10000,
        },
        {
            "place_name": "B",
            "rating": 5,
            "rating_count": 500,
            "tourism_visitors": 50000,
        },
    ]

    result = add_popularity_to_places(places)

    assert len(result) == 2
    assert "popularity_score" in result[0]
    assert "popularity_score" in result[1]