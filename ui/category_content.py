"""Curated, category-level copy used whenever a scraped source doesn't
supply a real description — gives every destination a meaningful "About"
line and a one-line "Famous for" instead of a blank/boilerplate placeholder.
"""

import re

CATEGORY_INFO = {
    "temple": {
        "famous_for": "Its architecture and spiritual significance",
        "about": (
            "{name} is known for its temple architecture and spiritual "
            "significance, drawing devotees and heritage enthusiasts alike."
        ),
    },
    "beach": {
        "famous_for": "Its coastline and sunset views",
        "about": (
            "{name} is known for its coastline and relaxed seaside "
            "atmosphere, popular for sunset views and a stroll by the water."
        ),
    },
    "waterfall": {
        "famous_for": "Its cascading waters and scenery",
        "about": (
            "{name} is known for its cascading waters and scenic "
            "surroundings, a favourite for nature walks and photography."
        ),
    },
    "hill": {
        "famous_for": "Cool weather and scenic viewpoints",
        "about": (
            "{name} is known for its cool weather, scenic viewpoints and "
            "trekking trails, making it a favoured hill destination."
        ),
    },
    "wildlife": {
        "famous_for": "Its biodiversity and wildlife sightings",
        "about": (
            "{name} is known for its rich biodiversity, offering visitors "
            "the chance to spot native and migratory wildlife."
        ),
    },
    "heritage": {
        "famous_for": "Its historical and architectural heritage",
        "about": (
            "{name} is known for its historical significance and "
            "well-preserved architecture, a notable heritage landmark."
        ),
    },
    "historical": {
        "famous_for": "Its place in Tamil Nadu's history",
        "about": (
            "{name} holds a notable place in Tamil Nadu's history and is "
            "known for its historical architecture and heritage value."
        ),
    },
    "nature": {
        "famous_for": "Its natural scenery and greenery",
        "about": (
            "{name} is known for its lush greenery and peaceful natural "
            "setting, a pleasant spot to unwind outdoors."
        ),
    },
    "cultural": {
        "famous_for": "Its cultural and local significance",
        "about": (
            "{name} is known for its cultural significance and local "
            "traditions, offering a glimpse into the region's heritage."
        ),
    },
}

DEFAULT_CATEGORY_INFO = {
    "famous_for": "Local sightseeing and photography",
    "about": (
        "{name} is one of Tamil Nadu's tourist destinations, worth a visit "
        "for sightseeing and exploring the local surroundings."
    ),
}

# Generic boilerplate injected by automated scrapers that add no real
# information for a user browsing the site — suppressed rather than shown.
GENERIC_SOURCE_DESCRIPTIONS = {
    "tourist location listed in wikidata.",
}


def category_info(category_name):
    return CATEGORY_INFO.get(
        str(category_name or "").strip().lower(),
        DEFAULT_CATEGORY_INFO,
    )


# Wikidata's short descriptions ("temple in India", "dam in Tamil Nadu,
# India", "waterfall") describe the item type, not the place.
def _is_type_only(description):
    text = description.strip().rstrip(".").lower()
    if not text:
        return False
    if len(text.split()) <= 3:
        return True
    return len(text) < 60 and text.endswith(("india", "tamil nadu"))


def resolve_description(raw_description, place_name, category_name):
    """Return a real description, or a category-appropriate fallback line."""
    cleaned = str(raw_description or "").strip()

    if cleaned.lower() in GENERIC_SOURCE_DESCRIPTIONS or _is_type_only(cleaned):
        cleaned = ""

    if cleaned:
        return cleaned

    return category_info(category_name)["about"].format(name=place_name)
