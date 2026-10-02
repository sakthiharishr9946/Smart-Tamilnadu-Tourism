from config.categories import TOURISM_CATEGORIES


def calculate_interest_score(
    place_category,
    preferred_categories,
):
    if not place_category:
        return 0.0

    if not preferred_categories:
        return 0.0

    if isinstance(preferred_categories, str):
        preferred_categories = [
            item.strip()
            for item in preferred_categories.split(",")
            if item.strip()
        ]

    normalized_category = str(
        place_category
    ).strip().lower()

    normalized_preferences = [
        str(item).strip().lower()
        for item in preferred_categories
    ]

    if normalized_category in normalized_preferences:
        return 1.0

    return 0.0


def calculate_category_similarity(
    place_category,
    preferred_categories,
):
    if not place_category or not preferred_categories:
        return 0.0

    if isinstance(preferred_categories, str):
        preferred_categories = [
            item.strip()
            for item in preferred_categories.split(",")
            if item.strip()
        ]

    category_groups = {
        "Temple": {"Temple", "Cultural", "Heritage", "Historical"},
        "Historical": {"Historical", "Heritage", "Cultural", "Temple"},
        "Heritage": {"Heritage", "Historical", "Cultural", "Temple"},
        "Cultural": {"Cultural", "Heritage", "Historical", "Temple"},
        "Nature": {"Nature", "Wildlife", "Waterfall", "Hill"},
        "Wildlife": {"Wildlife", "Nature", "Adventure"},
        "Waterfall": {"Waterfall", "Nature", "Adventure"},
        "Hill": {"Hill", "Nature", "Adventure"},
        "Adventure": {"Adventure", "Nature", "Wildlife"},
        "Beach": {"Beach", "Nature", "Adventure"},
    }

    for preferred in preferred_categories:
        if preferred not in TOURISM_CATEGORIES:
            continue

        related_categories = category_groups.get(
            preferred,
            {preferred},
        )

        if place_category in related_categories:
            if place_category == preferred:
                return 1.0

            return 0.6

    return 0.0


def match_user_interests(
    places,
    preferred_categories,
):
    if not places:
        return []

    results = []

    for place in places:
        place_data = dict(place)

        category = place_data.get(
            "category_name"
        )

        direct_score = calculate_interest_score(
            category,
            preferred_categories,
        )

        similarity_score = calculate_category_similarity(
            category,
            preferred_categories,
        )

        place_data["interest_score"] = max(
            direct_score,
            similarity_score,
        )

        results.append(place_data)

    return results