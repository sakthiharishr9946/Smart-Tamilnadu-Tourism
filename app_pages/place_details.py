import calendar
import datetime
from html import escape

import streamlit as st

from database.queries import (
    add_place_rating,
    get_festivals_for_place,
    get_place_by_id,
    get_place_images,
    get_place_ratings,
    get_place_sources,
)
from ui.components.map_view import render_map_view
from ui.components.rating import render_rating
from ui.components.crowd_badge import render_crowd_info
from ui.category_content import category_info, resolve_description
from ui.components.page_hero import render_page_hero
from services.crowd.estimator import estimate_crowd_level
from ui.data import clear_place_cache


def render_place_details(place_id):
    place = get_place_by_id(place_id)

    if not place:
        st.error("Tourist place not found.")
        return

    # Convert database row to dictionary
    place = dict(place)

    place_name = place.get(
        "place_name",
        "Tourist Place",
    )

    city = place.get("city_town") or place.get("city") or ""
    district = place.get("district") or "Tamil Nadu"
    location_text = f"{city}, {district}" if city else district

    render_page_hero(
        "Destination",
        place_name,
        f"📍 {location_text}",
        show_photos=False,
    )

    images = get_place_images(place_id)

    # Convert database rows to dictionaries
    images = [
        dict(image)
        for image in images
    ]

    images = [image for image in images if image.get("image_url")]
    if images:
        _render_photo(images[0], place_name)

    place_category_info = category_info(place.get("category_name"))

    col1, col2 = st.columns(2)

    with col1:
        st.markdown(
            """
            <div class="section-title">
                About the Destination
            </div>
            """,
            unsafe_allow_html=True,
        )

        description = resolve_description(
            place.get("description"),
            place_name,
            place.get("category_name"),
        )

        st.write(description)

    with col2:
        st.markdown(
            """
            <div class="section-title">
                Destination Details
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.write(
            f"**Category:** "
            f"{place.get('category_name') or 'Unknown'}"
        )

        st.write(
            f"**Famous for:** "
            f"{place_category_info['famous_for']}"
        )

        st.write(
            f"**City:** "
            f"{city or 'Not listed'}"
        )

        st.write(
            f"**District:** "
            f"{place.get('district') or 'Unknown'}"
        )

        entry_fee = place.get('entry_fee')
        entry_fee_text = f"₹{entry_fee:g}" if entry_fee else "Free / Not available"

        st.write(
            f"**Entry Fee:** "
            f"{entry_fee_text}"
        )

    festivals = [dict(festival) for festival in get_festivals_for_place(place_id, place.get("district"))]
    local_festivals = [f for f in festivals if f.get("relevance", 2) < 2]

    st.markdown(
        """
        <div class="section-title">
            Crowd Forecast
        </div>
        """,
        unsafe_allow_html=True,
    )

    crowd_level, _crowd_score = estimate_crowd_level(
        place.get("category_name"),
        festivals=local_festivals,
    )

    render_crowd_info(crowd_level)

    st.markdown(
        """
        <div class="section-title">
            Rating
        </div>
        """,
        unsafe_allow_html=True,
    )

    render_rating(
        place.get("rating", 0),
        place.get("rating_count", 0),
    )

    ratings = get_place_ratings(place_id)

    # Convert database rows to dictionaries
    ratings = [
        dict(rating)
        for rating in ratings
    ]

    if ratings:
        with st.expander(f"View Reviews ({len(ratings)})"):
            for review in ratings:
                rating_value = int(review.get("rating") or 0)
                when = str(review.get("rating_date") or "")[:10]
                st.write(f"{'★' * rating_value}{'☆' * (5 - rating_value)}  {when}")
                if review.get("review"):
                    st.write(review["review"])
                st.divider()

    _render_rating_form(place_id)

    latitude = place.get("latitude")
    longitude = place.get("longitude")

    if (
        latitude is not None
        and longitude is not None
    ):
        st.markdown(
            """
            <div class="section-title">
                Location
            </div>
            """,
            unsafe_allow_html=True,
        )

        if place.get("location_precision") == "locality":
            st.caption(
                f"📍 Approximate location: shown at the centre of {city or 'its village'}. "
                "Ask locally for the exact spot."
            )

        render_map_view(
            [place],
            zoom=13,
        )
    else:
        st.caption(f"📍 Exact map location not available yet. Located in {location_text}.")

    _render_festivals(festivals, district)
    _render_sources(get_place_sources(place_id))


def _render_rating_form(place_id):
    """Traveller ratings: the only free source of ratings for these places."""
    rated = st.session_state.setdefault("rated_places", set())
    if place_id in rated:
        st.caption("Thanks — your rating is included above.")
        return
    with st.expander("⭐ Been here? Rate this place"):
        with st.form(f"rate_{place_id}", clear_on_submit=True, border=False):
            stars = st.feedback("stars", key=f"stars_{place_id}")
            review = st.text_area("Short review (optional)", max_chars=500,
                                  placeholder="Crowd, cleanliness, best time to go…")
            if st.form_submit_button("Submit rating"):
                if stars is None:
                    st.warning("Pick 1 to 5 stars first.")
                else:
                    add_place_rating(place_id, stars + 1, review)  # st.feedback stars are 0-4
                    rated.add(place_id)
                    clear_place_cache()
                    st.rerun()


def _render_photo(image, place_name):
    """Destination photo with the credit line its licence requires."""
    url = escape(str(image["image_url"]), quote=True)
    # Commons "Artist" fields are sometimes whole paragraphs; the first
    # sentence names the author.
    author = str(image.get("image_author") or "").split(". ")[0].strip()
    if len(author) > 80:
        author = author[:77].rsplit(" ", 1)[0] + "…"
    credit_parts = [
        str(part) for part in (author, image.get("image_license"), image.get("image_source"))
        if part
    ]
    credit = escape(" · ".join(dict.fromkeys(credit_parts)))
    st.markdown(
        f'<figure class="place-photo">'
        f'<img src="{url}" alt="{escape(place_name, quote=True)}" referrerpolicy="no-referrer">'
        + (f'<figcaption>Photo: {credit}</figcaption>' if credit else "")
        + '</figure>',
        unsafe_allow_html=True,
    )


def _festival_when(festival):
    start = festival.get("start_date")
    if start:
        try:
            return datetime.date.fromisoformat(str(start)).strftime("%d %b %Y")
        except ValueError:
            return str(start)
    month = festival.get("month")
    if month:
        try:
            return calendar.month_name[int(month)]
        except (TypeError, ValueError, IndexError):
            pass
    return "Date varies"


def _next_occurrences(festivals):
    """One entry per festival - its earliest listed date - in date order.

    Holidays are stored for this year and next, so "Pongal" exists twice."""
    first = {}
    for festival in sorted(festivals, key=lambda f: str(f.get("start_date") or "9999")):
        first.setdefault(str(festival.get("festival_name") or "").strip().casefold(), festival)
    return list(first.values())


def _render_festivals(festivals, district, statewide_limit=6):
    today = datetime.date.today().isoformat()
    local = [f for f in festivals if f.get("relevance", 2) < 2]
    # Statewide festival holidays: only the next few upcoming dates.
    statewide = [f for f in festivals if f.get("relevance", 2) == 2 and str(f.get("start_date") or "") >= today]
    statewide = _next_occurrences(statewide)[:statewide_limit]
    local = _next_occurrences(local)
    if not local and not statewide:
        return

    st.markdown('<div class="section-title">Festivals &amp; Events</div>', unsafe_allow_html=True)
    groups = ((f"In {district} district", local), ("Upcoming across Tamil Nadu", statewide))
    for heading, items in groups:
        if not items:
            continue
        st.markdown(f"**{escape(heading)}**")
        rows = []
        for festival in items:
            description = festival.get("description") or ""
            rows.append(
                '<div class="festival-row">'
                f'<div class="festival-when">{escape(_festival_when(festival))}</div>'
                f'<div><div class="festival-name">{escape(str(festival.get("festival_name") or "Festival"))}</div>'
                + (f'<div class="festival-desc">{escape(description[:220])}{"…" if len(description) > 220 else ""}</div>'
                   if description else "")
                + '</div></div>'
            )
        st.markdown('<div class="festival-list">' + "".join(rows) + '</div>', unsafe_allow_html=True)


def _render_sources(sources):
    sources = [dict(source) for source in sources]
    if not sources:
        return
    items = []
    for source in sources:
        name = escape(str(source.get("source_name") or "Source"))
        url = str(source.get("source_url") or "")
        if url.startswith(("http://", "https://")):
            items.append(f'<a href="{escape(url, quote=True)}" target="_blank" rel="noopener">{name}</a>')
        else:
            items.append(name)
    st.markdown(
        '<div class="place-sources">Listed by: ' + " · ".join(items) + '</div>',
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    place_id = st.session_state.get(
        "selected_place_id"
    )

    if place_id:
        render_place_details(place_id)
    else:
        st.info(
            "Select a tourist place to view its details."
        )