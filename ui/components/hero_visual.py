from html import escape

import streamlit as st

from ui.data import has_photo, load_places

# Cards show the destination's photo when one was collected (Wikimedia
# Commons or an official tourism site) and fall back to the gradient
# category tile otherwise.
CATEGORY_GLYPHS = {
    "temple": "🛕",
    "beach": "🏖️",
    "hill": "⛰️",
    "waterfall": "💦",
    "wildlife": "🦌",
    "heritage": "🏛️",
    "historical": "🏺",
    "nature": "🌿",
    "cultural": "🎭",
    "adventure": "🧗",
}

DEFAULT_GLYPH = "📍"


def _pick_showcase_places(limit=5):
    """The most prominent photographed place of each category."""
    places = load_places()  # already ordered by prominence
    candidates = [p for p in places if has_photo(p)] or places

    by_category = {}
    for place in candidates:
        category = str(place.get("category_name") or "Other").strip()
        if category and category not in by_category:
            by_category[category] = place

    return list(by_category.values())[:limit]


def render_hero_3d_showcase():
    """Hover-cascade destination cards.

    A previous version used a rotating 3D ring, then a static fan — this
    replaces both with a fixed-layout gradient card (adapted from a
    Uiverse.io hover-cascade design) whose category glyph stays centered
    and whose rating/category/district reveal as stacked accent tiles on
    hover. Nothing here is positioned relative to a rotating axis, so it
    can't drift out of alignment the way the 3D ring did.
    """

    places = _pick_showcase_places()

    if not places:
        return

    cards = []
    for place in places:
        place_id = place.get("place_id")
        if place_id is None:
            continue

        category_raw = str(place.get("category_name") or "")
        glyph = CATEGORY_GLYPHS.get(category_raw.strip().lower(), DEFAULT_GLYPH)
        name = escape(str(place.get("place_name", "Tamil Nadu")))
        district = escape(str(place.get("district") or "Tamil Nadu"))
        category = escape(category_raw or "Destination")

        rating = place.get("rating") or 0
        try:
            rating = float(rating)
        except (TypeError, ValueError):
            rating = 0.0
        rating_label = f"⭐ {rating:.1f}" if rating > 0 else "New"

        if has_photo(place):
            image_url = escape(str(place["image_url"]), quote=True)
            background = (
                '<div class="hs-bg"></div>'
                f'<img class="hs-photo" src="{image_url}" alt="" loading="lazy" referrerpolicy="no-referrer">'
                '<div class="hs-shade"></div>'
            )
            logo = ""
        else:
            background = '<div class="hs-bg"></div>'
            logo = f'<div class="hs-logo">{glyph}</div>'

        cards.append(
            f'<a class="hs-card reveal" href="?place_id={place_id}" target="_self">'
            f'{background}'
            f'<div class="hs-name">{name}<span class="hs-district">{district}</span></div>'
            f'{logo}'
            f'<div class="hs-box hs-box1" title="Rating"><span class="hs-icon">{rating_label}</span></div>'
            f'<div class="hs-box hs-box2" title="{category}"><span class="hs-icon">{glyph}</span></div>'
            f'<div class="hs-box hs-box3" title="{district}"><span class="hs-icon">📍</span></div>'
            '<div class="hs-box hs-box4"></div>'
            '</a>'
        )

    html = '<div class="hs-row">' + "".join(cards) + '</div>'

    st.markdown(html, unsafe_allow_html=True)


def pick_photo_places(categories=None, limit=3, skip=0):
    """Most prominent photographed places, one per category in ``categories``
    order (or across all categories when none are given)."""
    places = [p for p in load_places() if has_photo(p)]
    chosen, seen_categories = [], set()
    wanted = [c.casefold() for c in (categories or [])]
    for place in places:
        category = str(place.get("category_name") or "").casefold()
        if wanted and category not in wanted:
            continue
        if category in seen_categories:
            continue
        seen_categories.add(category)
        chosen.append(place)
    if wanted:
        chosen.sort(key=lambda p: wanted.index(str(p.get("category_name") or "").casefold()))
    return chosen[skip:skip + limit]


def render_photo_cards(places):
    """Static version of the home hero cards (photo, name, district)."""
    cards = []
    for place in places:
        image_url = escape(str(place["image_url"]), quote=True)
        name = escape(str(place.get("place_name") or ""))
        district = escape(str(place.get("district") or ""))
        cards.append(
            f'<a class="hs-card reveal" href="?place_id={place.get("place_id")}" target="_self">'
            '<div class="hs-bg"></div>'
            f'<img class="hs-photo" src="{image_url}" alt="" loading="lazy" referrerpolicy="no-referrer">'
            '<div class="hs-shade"></div>'
            f'<div class="hs-name">{name}<span class="hs-district">{district}</span></div>'
            '</a>'
        )
    if cards:
        st.markdown('<div class="hs-row page-hero-cards">' + "".join(cards) + '</div>', unsafe_allow_html=True)
