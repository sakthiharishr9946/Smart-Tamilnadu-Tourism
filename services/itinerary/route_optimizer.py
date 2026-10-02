from services.nearby.distance import calculate_distance


def calculate_route_distance(places):
    if not places or len(places) < 2:
        return 0.0

    total_distance = 0.0

    for index in range(len(places) - 1):
        current = places[index]
        next_place = places[index + 1]

        distance = calculate_distance(
            current.get("latitude"),
            current.get("longitude"),
            next_place.get("latitude"),
            next_place.get("longitude"),
        )

        if distance is not None:
            total_distance += distance

    return round(total_distance, 2)


def optimize_route(places, start_latitude=None, start_longitude=None):
    if not places:
        return []

    remaining = [dict(place) for place in places]
    optimized = []

    if start_latitude is not None and start_longitude is not None:
        current_latitude = start_latitude
        current_longitude = start_longitude
    else:
        first = remaining.pop(0)
        optimized.append(first)

        current_latitude = first.get("latitude")
        current_longitude = first.get("longitude")

    while remaining:
        nearest_index = None
        nearest_distance = float("inf")

        for index, place in enumerate(remaining):
            distance = calculate_distance(
                current_latitude,
                current_longitude,
                place.get("latitude"),
                place.get("longitude"),
            )

            if distance is not None and distance < nearest_distance:
                nearest_distance = distance
                nearest_index = index

        if nearest_index is None:
            optimized.extend(remaining)
            break

        next_place = remaining.pop(nearest_index)
        optimized.append(next_place)

        current_latitude = next_place.get("latitude")
        current_longitude = next_place.get("longitude")

    return optimized


def optimize_and_calculate_route(
    places,
    start_latitude=None,
    start_longitude=None,
):
    optimized_places = optimize_route(
        places,
        start_latitude,
        start_longitude,
    )

    total_distance = calculate_route_distance(
        optimized_places
    )

    return optimized_places, total_distance