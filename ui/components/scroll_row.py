from html import escape

import streamlit as st

from ui.category_content import resolve_description
from ui.components.hero_visual import CATEGORY_GLYPHS, DEFAULT_GLYPH
from ui.data import has_photo

# Streamlit widgets can't live inside a hand-built horizontal-scroll strip,
# so each tile is a plain <a href="?place_id=..."> instead of a st.button.
# app.py reads that query param on every rerun and maps it onto the same
# session_state["selected_place_id"] the rest of the app already uses.


def render_scroll_row(title, places, subtitle=None):
    if not places:
        return

    tiles = []
    for place in places:
        place_id = place.get("place_id")
        if place_id is None:
            continue

        category_raw = str(place.get("category_name") or "")
        glyph = CATEGORY_GLYPHS.get(category_raw.strip().lower(), DEFAULT_GLYPH)

        name = escape(str(place.get("place_name", "Tamil Nadu")))
        district = escape(str(place.get("district") or "Tamil Nadu"))
        full_blurb = resolve_description(
            place.get("description"),
            place.get("place_name", "This destination"),
            place.get("category_name"),
        )
        truncated = len(full_blurb) > 90
        blurb = escape(full_blurb[:90]) + ("&hellip;" if truncated else "")

        if has_photo(place):
            image_url = escape(str(place["image_url"]), quote=True)
            # The glyph sits behind the photo, so a photo that fails to load
            # still leaves a meaningful tile.
            visual = (
                f'<div class="hrow-tile-photo"><span class="hrow-tile-photo-glyph">{glyph}</span>'
                f'<img src="{image_url}" alt="{name}" loading="lazy" referrerpolicy="no-referrer"></div>'
            )
        else:
            visual = f'<div class="hrow-tile-visual">{glyph}</div>'

        tiles.append(
            f'<a class="hrow-tile" href="?place_id={place_id}" target="_self">'
            f'{visual}'
            f'<div class="hrow-tile-name">{name}</div>'
            f'<div class="hrow-tile-meta">{district}</div>'
            f'<div class="hrow-tile-blurb">{blurb}</div>'
            '</a>'
        )

    subtitle_html = f'<span class="hrow-subtitle">{escape(subtitle)}</span>' if subtitle else ""
    html = (
        f'<div class="hrow reveal">'
        f'<div class="hrow-title">{escape(title)}{subtitle_html}</div>'
        '<div class="hrow-track">' + "".join(tiles) + '</div>'
        '</div>'
    )

    st.markdown(html, unsafe_allow_html=True)
