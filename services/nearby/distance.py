from math import radians, sin, cos, sqrt, atan2


EARTH_RADIUS_KM = 6371.0


def calculate_distance(
    latitude1,
    longitude1,
    latitude2,
    longitude2,
):
    try:
        latitude1 = float(latitude1)
        longitude1 = float(longitude1)
        latitude2 = float(latitude2)
        longitude2 = float(longitude2)
    except (TypeError, ValueError):
        return None

    lat1 = radians(latitude1)
    lon1 = radians(longitude1)
    lat2 = radians(latitude2)
    lon2 = radians(longitude2)

    delta_latitude = lat2 - lat1
    delta_longitude = lon2 - lon1

    value = (
        sin(delta_latitude / 2) ** 2
        + cos(lat1)
        * cos(lat2)
        * sin(delta_longitude / 2) ** 2
    )

    value = min(1.0, max(0.0, value))

    distance = 2 * atan2(
        sqrt(value),
        sqrt(1 - value),
    )

    return EARTH_RADIUS_KM * distance


def add_distance_to_places(
    places,
    latitude,
    longitude,
):
    if places is None:
        return []

    results = []

    for place in places:
        place_data = dict(place)

        distance = calculate_distance(
            latitude,
            longitude,
            place_data.get("latitude"),
            place_data.get("longitude"),
        )

        place_data["distance_km"] = distance
        results.append(place_data)

    return results


def filter_by_distance(
    places,
    max_distance_km,
):
    if places is None:
        return []

    try:
        max_distance_km = float(max_distance_km)
    except (TypeError, ValueError):
        return []

    return [
        place
        for place in places
        if place.get("distance_km") is not None
        and place["distance_km"] <= max_distance_km
    ]


def sort_by_distance(places):
    if places is None:
        return []

    return sorted(
        places,
        key=lambda place: (
            place.get("distance_km")
            if place.get("distance_km") is not None
            else float("inf")
        ),
    )