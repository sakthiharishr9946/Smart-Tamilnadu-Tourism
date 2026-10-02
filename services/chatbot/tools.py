from database.queries import (
    get_all_places,
    get_place_by_id,
    search_places,
    get_places_by_category,
    get_places_by_district,
)


def search_tourist_places(search_term=""):
    if not search_term or not str(search_term).strip():
        return get_all_places()

    return search_places(
        str(search_term).strip()
    )


def get_place_information(place_id_or_name):
    if place_id_or_name is None:
        return None

    if isinstance(place_id_or_name, int):
        return get_place_by_id(
            place_id_or_name
        )

    text = str(place_id_or_name).strip()

    if not text:
        return None

    if text.isdigit():
        place = get_place_by_id(
            int(text)
        )

        if place:
            return place

    results = search_places(text)

    if results:
        return results[0]

    return None


def get_places_by_tourism_category(category_id):
    if category_id is None:
        return []

    try:
        category_id = int(category_id)
    except (TypeError, ValueError):
        return []

    return get_places_by_category(
        category_id
    )


def get_places_by_location(district):
    if not district or not str(district).strip():
        return []

    return get_places_by_district(
        str(district).strip()
    )


def get_chatbot_tools():
    return {
        "search_tourist_places": search_tourist_places,
        "get_place_information": get_place_information,
        "get_places_by_tourism_category": (
            get_places_by_tourism_category
        ),
        "get_places_by_location": (
            get_places_by_location
        ),
    }