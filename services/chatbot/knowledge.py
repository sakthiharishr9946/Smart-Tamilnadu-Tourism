from database.queries import (
    get_all_categories,
    get_all_places,
    get_place_by_id,
    get_place_festivals,
    get_holidays,
)


KNOWLEDGE = {
    "greeting": (
        "Welcome to Smart Tamilnadu Tourism! "
        "I can help you explore tourist destinations, "
        "plan trips, estimate budgets and discover "
        "Tamil Nadu's cultural attractions."
    ),
    "tamilnadu": (
        "Tamil Nadu offers a wide range of tourism "
        "destinations including temples, beaches, "
        "hill stations, waterfalls, wildlife areas, "
        "heritage sites and cultural attractions."
    ),
    "help": (
        "You can ask about tourist places, categories, "
        "festivals, holidays, destinations, itineraries "
        "or travel budgets."
    ),
}


def get_static_knowledge(message):
    if not message:
        return None

    text = message.lower().strip()

    if any(
        word in text
        for word in ["hello", "hi", "hey", "vanakkam"]
    ):
        return KNOWLEDGE["greeting"]

    if any(
        phrase in text
        for phrase in [
            "about tamil nadu",
            "about tamilnadu",
            "tamil nadu tourism",
            "tamilnadu tourism",
        ]
    ):
        return KNOWLEDGE["tamilnadu"]

    if any(
        word in text
        for word in [
            "help",
            "what can you do",
            "features",
        ]
    ):
        return KNOWLEDGE["help"]

    return None


def search_knowledge(message):
    static_response = get_static_knowledge(message)

    if static_response:
        return static_response

    if not message:
        return None

    text = message.lower().strip()

    if "category" in text or "categories" in text:
        categories = get_all_categories()

        if not categories:
            return None

        names = [
            category["category_name"]
            for category in categories
        ]

        return (
            "Available tourism categories:\n\n"
            + "\n".join(
                f"{index}. {name}"
                for index, name in enumerate(
                    names,
                    start=1,
                )
            )
        )

    if "holiday" in text or "holidays" in text:
        holidays = get_holidays()

        if not holidays:
            return None

        names = [
            holiday["holiday_name"]
            for holiday in holidays[:10]
        ]

        return (
            "Some available holidays are:\n\n"
            + "\n".join(
                f"{index}. {name}"
                for index, name in enumerate(
                    names,
                    start=1,
                )
            )
        )

    if "festival" in text or "festivals" in text:
        places = get_all_places()

        festival_places = []

        for place in places:
            place_id = place["place_id"]

            festivals = get_place_festivals(
                place_id
            )

            if festivals:
                festival_places.extend(
                    festivals
                )

        if not festival_places:
            return None

        names = list(
            dict.fromkeys(
                festival["festival_name"]
                for festival in festival_places
                if festival.get("festival_name")
            )
        )

        return (
            "Festivals available in the tourism "
            "database:\n\n"
            + "\n".join(
                f"{index}. {name}"
                for index, name in enumerate(
                    names[:10],
                    start=1,
                )
            )
        )

    return None


def get_place_knowledge(place_id):
    place = get_place_by_id(place_id)

    if not place:
        return None

    festivals = get_place_festivals(
        place_id
    )

    return {
        "place": dict(place),
        "festivals": [
            dict(festival)
            for festival in festivals
        ],
    }