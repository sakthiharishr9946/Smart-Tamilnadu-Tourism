"""Category mosaic for the Explore page.

One photo tile per tourism category: the category's most prominent
photographed place as the image, how many destinations it has, and its
best-known place by name. Tiles are links (?category=...) that the
Explore page turns into a category filter.
"""

from html import escape
from urllib.parse import quote

import streamlit as st

from config.categories import TOURISM_CATEGORIES
from ui.components.hero_visual import CATEGORY_GLYPHS, DEFAULT_GLYPH
from ui.data import has_photo

CATEGORY_LINES = {
    "Temple": "Gopurams, mandapams and living shrines",
    "Cultural": "Churches, mosques, dargahs and local life",
    "Heritage": "Museums, memorials and monuments",
    "Nature": "Lakes, dams, gardens and forests",
    "Historical": "Forts, palaces and ancient sites",
    "Hill": "Hill stations, peaks and viewpoints",
    "Waterfall": "Falls from Courtallam to Hogenakkal",
    "Beach": "The Coromandel and Gulf of Mannar coasts",
    "Wildlife": "Sanctuaries, reserves and bird lakes",
    "Adventure": "Boating, trekking and theme parks",
}


def _category_summaries(places):
    summaries = {}
    for place in places:  # already ordered by prominence
        category = str(place.get("category_name") or "").strip()
        if not category:
            continue
        summary = summaries.setdefault(category, {"count": 0, "top": None, "cover": None})
        summary["count"] += 1
        if summary["top"] is None:
            summary["top"] = place
        if summary["cover"] is None and has_photo(place):
            summary["cover"] = place
    order = {name: index for index, name in enumerate(TOURISM_CATEGORIES)}
    return sorted(summaries.items(), key=lambda item: (-item[1]["count"], order.get(item[0], 99)))


def render_category_showcase(places, selected=None):
    summaries = _category_summaries(places)
    if not summaries:
        return

    tiles = []
    for index, (category, summary) in enumerate(summaries):
        glyph = CATEGORY_GLYPHS.get(category.lower(), DEFAULT_GLYPH)
        cover = summary["cover"]
        image = (
            f'<img src="{escape(str(cover["image_url"]), quote=True)}" alt="" loading="lazy" '
            'referrerpolicy="no-referrer">'
            if cover else f'<span class="cat-glyph">{glyph}</span>'
        )
        top_name = escape(str((summary["top"] or {}).get("place_name") or ""))
        count = summary["count"]
        selected_class = " cat-tile-selected" if selected == category else ""
        tiles.append(
            f'<a class="cat-tile{selected_class}" href="?category={quote(category)}" target="_self" '
            f'style="--i:{index}" aria-label="{escape(category)}: {count} destinations">'
            f'<div class="cat-media">{image}</div>'
            '<div class="cat-shade"></div>'
            '<div class="cat-body">'
            f'<div class="cat-count">{count:,} places</div>'
            f'<div class="cat-name">{escape(category)}</div>'
            f'<div class="cat-line">{escape(CATEGORY_LINES.get(category, ""))}</div>'
            + (f'<div class="cat-top">Start with {top_name}</div>' if top_name else "")
            + '</div></a>'
        )

    st.markdown(
        '<div class="cat-section">'
        '<div class="section-title">Explore by category</div>'
        '<div class="cat-grid">' + "".join(tiles) + '</div>'
        '</div>',
        unsafe_allow_html=True,
    )
