"""Cached place data shared by UI pages.

Loading every place (several thousand rows, each with an image sub-query)
on every Streamlit rerun made the Explore page slow, so the UI reads one
cached copy. ``clear_place_cache`` must be called after a data refresh.
"""

import streamlit as st

from database.queries import get_all_places

# Places are already ordered by prominence (popularity_score DESC).
CACHE_SECONDS = 600


@st.cache_data(ttl=CACHE_SECONDS, show_spinner=False)
def load_places():
    return [dict(place) for place in get_all_places()]


def clear_place_cache():
    load_places.clear()


def has_photo(place):
    return bool(str(place.get("image_url") or "").startswith(("http://", "https://")))
