TOURISM_CATEGORIES = [
    "Temple",
    "Beach",
    "Hill",
    "Waterfall",
    "Wildlife",
    "Historical",
    "Heritage",
    "Adventure",
    "Nature",
    "Cultural",
]

CATEGORY_DESCRIPTIONS = {
    "Temple": "Ancient and famous temples across Tamil Nadu.",
    "Beach": "Coastal destinations and scenic beaches.",
    "Hill": "Hill stations and mountain destinations.",
    "Waterfall": "Waterfalls and natural water attractions.",
    "Wildlife": "Wildlife sanctuaries, reserves and nature parks.",
    "Historical": "Places with historical importance and significance.",
    "Heritage": "Heritage sites, monuments and traditional locations.",
    "Adventure": "Destinations suitable for adventure activities.",
    "Nature": "Natural landscapes, forests and scenic locations.",
    "Cultural": "Places representing Tamil Nadu's culture and traditions.",
}

CATEGORY_ICONS = {
    "Temple": "🛕",
    "Beach": "🏖️",
    "Hill": "⛰️",
    "Waterfall": "💧",
    "Wildlife": "🦌",
    "Historical": "🏛️",
    "Heritage": "🏰",
    "Adventure": "🧗",
    "Nature": "🌿",
    "Cultural": "🎭",
}

def get_categories():
    return TOURISM_CATEGORIES.copy()

def get_category_description(category):
    return CATEGORY_DESCRIPTIONS.get(category, "")

def get_category_icon(category):
    return CATEGORY_ICONS.get(category, "📍")