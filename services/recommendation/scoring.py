from config.search_config import (
    DISTANCE_WEIGHT,
    RATING_WEIGHT,
    POPULARITY_WEIGHT,
    INTEREST_WEIGHT,
    SEASON_WEIGHT,
    RATING_CONFIDENCE_WEIGHT,
)


def normalize_score(value, minimum=0.0, maximum=5.0):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return 0.0

    if maximum == minimum:
        return 0.0

    score = (value - minimum) / (maximum - minimum)

    return max(0.0, min(1.0, score))


def distance_score(distance_km):
    if distance_km is None:
        return 0.0

    try:
        distance_km = float(distance_km)
    except (TypeError, ValueError):
        return 0.0

    if distance_km <= 0:
        return 1.0

    return 1.0 / (1.0 + distance_km / 10.0)


def calculate_recommendation_score(
    place,
    interest_score=0.0,
    season_score=0.0,
):
    distance = distance_score(
        place.get("distance_km")
    )

    rating = normalize_score(
        place.get("rating", 0)
    )

    popularity = normalize_score(
        place.get("popularity_score", 0),
        maximum=100.0,
    )

    if interest_score == 0.0:
        interest_score = place.get("interest_score", 0.0)

    interest = normalize_score(interest_score, maximum=1.0)

    season = normalize_score(season_score, maximum=1.0)

    rating_confidence = normalize_score(place.get("rating_confidence", 0), maximum=1.0)

    score = (
        distance * DISTANCE_WEIGHT
        + rating * RATING_WEIGHT
        + popularity * POPULARITY_WEIGHT
        + interest * INTEREST_WEIGHT
        + season * SEASON_WEIGHT
        + rating_confidence * RATING_CONFIDENCE_WEIGHT
    )

    try:
        status_suitability = float(place.get("status_suitability", 1.0))
    except (TypeError, ValueError):
        status_suitability = 1.0
    return round(score * max(0.0, min(1.0, status_suitability)) * 100, 2)


def score_places(
    places,
    interest_scores=None,
    season_scores=None,
):
    if not places:
        return []

    interest_scores = interest_scores or {}
    season_scores = season_scores or {}

    scored_places = []

    for place in places:
        place_data = dict(place)

        place_id = place_data.get("place_id")

        interest_score = interest_scores.get(
            place_id,
            0.0,
        )

        season_score = season_scores.get(
            place_id,
            0.0,
        )

        place_data["recommendation_score"] = (
            calculate_recommendation_score(
                place_data,
                interest_score,
                season_score,
            )
        )

        scored_places.append(place_data)

    return scored_places
