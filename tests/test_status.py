from services.recommendation.scoring import calculate_recommendation_score
from services.status.place_status import status_suitability


def test_unsuitable_status_reduces_recommendation_score():
    place = {
        "rating": 4.5,
        "rating_count": 500,
        "popularity_score": 80,
        "rating_confidence": 0.5,
        "interest_score": 1,
    }
    suitable = calculate_recommendation_score({**place, "status_suitability": 1})
    unsuitable = calculate_recommendation_score({**place, "status_suitability": 0.2})
    assert unsuitable < suitable


def test_dry_status_is_unsuitable():
    assert status_suitability("Dry") < 1
