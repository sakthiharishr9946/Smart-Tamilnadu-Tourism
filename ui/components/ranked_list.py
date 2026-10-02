from html import escape

import streamlit as st

from ui.category_content import resolve_description
from ui.components.crowd_badge import get_crowd_badge_class, get_crowd_icon
from services.crowd.estimator import estimate_crowd_level
from ui.components.hero_visual import CATEGORY_GLYPHS, DEFAULT_GLYPH
from ui.data import has_photo


def render_ranked_list(places):
    """Editorial ranked list — a numbered, divider-separated list instead of
    a grid of bordered cards. Each row is a plain <a href="?place_id=..">
    link, the same click-through pattern used by the horizontal scroll rows.
    """
    if not places:
        return

    rows = []
    for index, place in enumerate(places, start=1):
        place_id = place.get("place_id")
        if place_id is None:
            continue

        place_name_raw = str(place.get("place_name", "Unknown Place"))
        name = escape(place_name_raw)
        district = escape(str(place.get("district") or "Tamil Nadu"))
        category_raw = str(place.get("category_name") or "Tourist Attraction")
        category = escape(category_raw)

        description = escape(
            resolve_description(
                place.get("description"),
                place_name_raw,
                place.get("category_name"),
            )
        )

        crowd_level, _crowd_score = estimate_crowd_level(place.get("category_name"))
        crowd_class = get_crowd_badge_class(crowd_level)
        crowd_icon = get_crowd_icon(crowd_level)

        rating = place.get("rating") or 0
        try:
            rating = float(rating)
        except (TypeError, ValueError):
            rating = 0.0
        rating_html = (
            f'<span class="rank-rating">⭐ {rating:.1f}</span>'
            if rating > 0
            else '<span class="rank-rating rank-rating-empty">Not yet rated</span>'
        )

        thumb = (
            f'<img class="rank-thumb" src="{escape(str(place["image_url"]), quote=True)}" alt="" '
            'loading="lazy" referrerpolicy="no-referrer">'
            if has_photo(place)
            else f'<div class="rank-thumb rank-thumb-empty">{CATEGORY_GLYPHS.get(category_raw.strip().lower(), DEFAULT_GLYPH)}</div>'
        )

        rows.append(
            f'<a class="rank-item reveal" href="?place_id={place_id}" target="_self">'
            f'<div class="rank-number">{index:02d}</div>'
            f'{thumb}'
            '<div class="rank-body">'
            f'<div class="rank-name">{name}</div>'
            f'<div class="rank-meta">{category} &middot; {district}</div>'
            f'<div class="rank-desc">{description}</div>'
            '</div>'
            '<div class="rank-badges">'
            f'{rating_html}'
            f'<span class="{crowd_class}">{crowd_icon} {escape(str(crowd_level))}</span>'
            '</div>'
            '</a>'
        )

    st.markdown('<div class="rank-list">' + "".join(rows) + '</div>', unsafe_allow_html=True)
