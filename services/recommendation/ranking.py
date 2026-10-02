from config.search_config import MAX_RECOMMENDATIONS


def rank_places(places, limit=MAX_RECOMMENDATIONS):
    if not places:
        return []

    ranked_places = sorted(
        places,
        key=lambda place: place.get(
            "recommendation_score",
            0
        ),
        reverse=True,
    )

    return ranked_places[:limit]


def rank_by_rating(places, limit=MAX_RECOMMENDATIONS):
    if not places:
        return []

    ranked_places = sorted(
        places,
        key=lambda place: place.get(
            "rating",
            0
        ),
        reverse=True,
    )

    return ranked_places[:limit]


def rank_by_popularity(places, limit=MAX_RECOMMENDATIONS):
    if not places:
        return []

    ranked_places = sorted(
        places,
        key=lambda place: place.get(
            "popularity_score",
            0
        ),
        reverse=True,
    )

    return ranked_places[:limit]


def rank_by_distance(places, limit=MAX_RECOMMENDATIONS):
    if not places:
        return []

    ranked_places = sorted(
        places,
        key=lambda place: (
            place.get("distance_km")
            if place.get("distance_km") is not None
            else float("inf")
        ),
    )

    return ranked_places[:limit]