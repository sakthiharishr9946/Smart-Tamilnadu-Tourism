from config.search_config import (
    INITIAL_RADIUS_KM,
    RADIUS_INCREMENT_KM,
    MAX_RADIUS_KM,
    MIN_RESULTS,
)
from services.nearby.distance import (
    add_distance_to_places,
    filter_by_distance,
    sort_by_distance,
)


def adaptive_search(
    places,
    latitude,
    longitude,
    min_results=MIN_RESULTS,
    initial_radius=INITIAL_RADIUS_KM,
    radius_increment=RADIUS_INCREMENT_KM,
    max_radius=MAX_RADIUS_KM,
):
    if places is None:
        return [], initial_radius

    try:
        min_results = int(min_results)
        radius = float(initial_radius)
        radius_increment = float(radius_increment)
        max_radius = float(max_radius)
    except (TypeError, ValueError):
        return [], initial_radius

    places_with_distance = add_distance_to_places(
        places,
        latitude,
        longitude,
    )

    while radius <= max_radius:
        nearby_places = filter_by_distance(
            places_with_distance,
            radius,
        )

        nearby_places = sort_by_distance(
            nearby_places
        )

        if len(nearby_places) >= min_results:
            return nearby_places, radius

        if radius >= max_radius:
            return nearby_places, radius

        radius += radius_increment
        radius = min(radius, max_radius)

    return [], max_radius


def search_nearby_places(
    places,
    latitude,
    longitude,
    radius_km=INITIAL_RADIUS_KM,
):
    places_with_distance = add_distance_to_places(
        places,
        latitude,
        longitude,
    )

    nearby_places = filter_by_distance(
        places_with_distance,
        radius_km,
    )

    return sort_by_distance(nearby_places)