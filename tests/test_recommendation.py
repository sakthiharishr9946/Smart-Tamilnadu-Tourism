from services.recommendation.scoring import (
    normalize_score,
    distance_score,
    calculate_recommendation_score,
    score_places,
)


def test_normalize_score():
    assert normalize_score(0) == 0
    assert normalize_score(5) == 1
    assert normalize_score(2.5) == 0.5


def test_normalize_score_out_of_range():
    assert normalize_score(10) == 1
    assert normalize_score(-5) == 0


def test_distance_score():
    assert distance_score(0) == 1
    assert distance_score(10) == 0.5


def test_invalid_distance_score():
    assert distance_score(None) == 0


def test_recommendation_score():
    place = {
        "distance_km": 5,
        "rating": 4.5,
        "popularity_score": 80,
        "rating_confidence": 0.8,
    }

    score = calculate_recommendation_score(
        place,
        interest_score=1,
        season_score=1,
    )

    assert 0 <= score <= 100


def test_score_places():
    places = [
        {
            "place_id": 1,
            "place_name": "Temple",
            "distance_km": 5,
            "rating": 4.5,
            "popularity_score": 80,
            "rating_confidence": 0.8,
        }
    ]

    result = score_places(
        places,
        interest_scores={1: 1},
        season_scores={1: 1},
    )

    assert len(result) == 1
    assert "recommendation_score" in result[0]