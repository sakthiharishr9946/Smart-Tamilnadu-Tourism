def calculate_rating_confidence(
    rating_count,
    max_reviews=1000,
):
    try:
        rating_count = float(rating_count)
        max_reviews = float(max_reviews)
    except (TypeError, ValueError):
        return 0.0

    if rating_count <= 0:
        return 0.0

    if max_reviews <= 0:
        return 0.0

    confidence = rating_count / max_reviews

    return round(
        min(confidence, 1.0),
        4,
    )


def calculate_weighted_rating(
    rating,
    rating_count,
    minimum_rating=3.5,
    minimum_reviews=10,
):
    try:
        rating = float(rating)
        rating_count = int(rating_count)
    except (TypeError, ValueError):
        return 0.0

    if rating_count <= 0:
        return 0.0

    confidence = calculate_rating_confidence(
        rating_count
    )

    weighted_rating = (
        rating * confidence
        + minimum_rating * (1 - confidence)
    )

    if rating_count < minimum_reviews:
        weighted_rating *= 0.9

    return round(
        weighted_rating,
        4,
    )


def add_rating_confidence(place):
    if place is None:
        return {}

    place_data = dict(place)

    rating = place_data.get(
        "rating",
        0,
    )

    rating_count = place_data.get(
        "rating_count",
        0,
    )

    place_data["rating_confidence"] = (
        calculate_rating_confidence(
            rating_count
        )
    )

    place_data["weighted_rating"] = (
        calculate_weighted_rating(
            rating,
            rating_count,
        )
    )

    return place_data


def add_rating_confidence_to_places(places):
    if not places:
        return []

    return [
        add_rating_confidence(place)
        for place in places
    ]