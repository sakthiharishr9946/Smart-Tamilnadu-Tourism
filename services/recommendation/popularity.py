def calculate_popularity_score(
    rating=0,
    rating_count=0,
    tourism_visitors=0,
):
    try:
        rating = float(rating)
        rating_count = float(rating_count)
        tourism_visitors = float(tourism_visitors)
    except (TypeError, ValueError):
        return 0.0

    rating_score = max(0.0, min(rating / 5.0, 1.0))

    review_score = min(
        rating_count / 1000.0,
        1.0,
    )

    visitor_score = min(
        tourism_visitors / 100000.0,
        1.0,
    )

    popularity = (
        rating_score * 0.4
        + review_score * 0.3
        + visitor_score * 0.3
    )

    return round(popularity * 100, 2)


def add_popularity_score(place):
    place_data = dict(place)

    calculated = calculate_popularity_score(
        rating=place_data.get("rating", 0),
        rating_count=place_data.get(
            "rating_count",
            0,
        ),
        tourism_visitors=place_data.get(
            "tourism_visitors",
            0,
        ),
    )
    # Ratings and visitor counts are usually unavailable; never let the
    # rating-based formula erase the prominence score stored by the data
    # refresh (services/data_updates.py).
    try:
        stored = float(place_data.get("popularity_score") or 0)
    except (TypeError, ValueError):
        stored = 0.0
    place_data["popularity_score"] = max(calculated, stored)

    return place_data


def add_popularity_to_places(places):
    if not places:
        return []

    return [
        add_popularity_score(place)
        for place in places
    ]