LOW_THRESHOLD = 0.33
MEDIUM_THRESHOLD = 0.66


def classify_crowd(value):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return "Unknown"

    if value < 0 or value > 1:
        return "Unknown"

    if value <= LOW_THRESHOLD:
        return "Low"

    if value <= MEDIUM_THRESHOLD:
        return "Medium"

    return "High"


def classify_crowd_count(
    crowd_count,
    low_limit,
    high_limit,
):
    try:
        crowd_count = float(crowd_count)
        low_limit = float(low_limit)
        high_limit = float(high_limit)
    except (TypeError, ValueError):
        return "Unknown"

    if crowd_count < 0:
        return "Unknown"

    if low_limit < 0 or high_limit < 0:
        return "Unknown"

    if low_limit > high_limit:
        return "Unknown"

    if crowd_count <= low_limit:
        return "Low"

    if crowd_count <= high_limit:
        return "Medium"

    return "High"


def get_crowd_level_from_probability(
    probability,
):
    return classify_crowd(probability)


def get_crowd_description(level):
    descriptions = {
        "Low": (
            "Less crowded and suitable for a comfortable visit."
        ),
        "Medium": (
            "Moderately crowded. Plan your visit accordingly."
        ),
        "High": (
            "Highly crowded. Consider visiting at another time."
        ),
        "Unknown": (
            "Crowd information is currently unavailable."
        ),
    }

    return descriptions.get(
        level,
        descriptions["Unknown"],
    )