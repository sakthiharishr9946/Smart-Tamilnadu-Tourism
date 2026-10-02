from services.recommendation.rating_confidence import (
    calculate_rating_confidence,
    calculate_weighted_rating,
    add_rating_confidence,
    add_rating_confidence_to_places,
)


def test_rating_confidence():
    confidence = calculate_rating_confidence(500)

    assert confidence == 0.5


def test_rating_confidence_maximum():
    confidence = calculate_rating_confidence(2000)

    assert confidence == 1.0


def test_rating_confidence_zero():
    confidence = calculate_rating_confidence(0)

    assert confidence == 0.0


def test_weighted_rating():
    rating = calculate_weighted_rating(
        rating=4.5,
        rating_count=1000,
    )

    assert rating == 4.5


def test_weighted_rating_with_few_reviews():
    rating = calculate_weighted_rating(
        rating=5,
        rating_count=5,
    )

    assert rating < 5


def test_add_rating_confidence():
    place = {
        "place_name": "Temple",
        "rating": 4.5,
        "rating_count": 500,
    }

    result = add_rating_confidence(place)

    assert "rating_confidence" in result
    assert "weighted_rating" in result


def test_add_rating_confidence_to_places():
    places = [
        {
            "place_name": "A",
            "rating": 4,
            "rating_count": 100,
        },
        {
            "place_name": "B",
            "rating": 4.5,
            "rating_count": 500,
        },
    ]

    result = add_rating_confidence_to_places(places)

    assert len(result) == 2
    assert "rating_confidence" in result[0]
    assert "weighted_rating" in result[1]