from html import escape

import streamlit as st

from ui.category_content import category_info, resolve_description
from ui.data import has_photo


def render_itinerary_timeline(schedule):
    if not schedule:
        st.info("No itinerary schedule available.")
        return

    for item in schedule:
        place = item.get("place", {})

        place_name_raw = str(place.get("place_name", "Unknown Place"))
        place_name = escape(place_name_raw)

        start_time = item.get("start_time", "")
        end_time = item.get("end_time", "")
        duration = item.get("duration_minutes", 0)

        city = place.get("city_town")
        district_raw = str(place.get("district") or "Tamil Nadu")
        location_raw = f"{city}, {district_raw}" if city else district_raw
        location = escape(location_raw)

        category_raw = str(place.get("category_name") or "Tourist Attraction")
        category = escape(category_raw)

        full_description = resolve_description(
            place.get("description"),
            place_name_raw,
            place.get("category_name"),
        )
        if len(full_description) > 260:
            full_description = full_description[:257].rsplit(" ", 1)[0] + "…"
        description = escape(full_description)

        photo_html = (
            f'<img class="timeline-photo" src="{escape(str(place["image_url"]), quote=True)}" '
            f'alt="{place_name}" loading="lazy" referrerpolicy="no-referrer">'
            if has_photo(place) else ""
        )

        famous_for = escape(category_info(place.get("category_name"))["famous_for"])

        entry_fee = place.get("entry_fee")
        entry_fee_text = f"₹{entry_fee:g}" if entry_fee else "Free / Not available"

        st.markdown(
            f"""
            <div class="timeline-item reveal"><div class="timeline-row"><div class="timeline-text">
                <div class="timeline-time">
                    {start_time} - {end_time}
                </div>
                <div class="timeline-title">
                    {place_name}
                </div>
                <div class="place-card-location">
                    📍 {location} • {category}
                </div>
                <div class="place-card-description">
                    {description}
                </div>
                <div class="place-card-description">
                    <strong>Famous for:</strong> {famous_for}
                </div>
                <div class="place-card-description">
                    Visit duration: {duration} minutes
                    &nbsp;•&nbsp; Entry fee: {entry_fee_text}
                </div>
            </div>{photo_html}</div></div>
            """,
            unsafe_allow_html=True,
        )


def render_day_timeline(
    day_number,
    schedule,
):
    st.markdown(
        f"""
        <div class="section-title">
            Day {day_number}
        </div>
        """,
        unsafe_allow_html=True,
    )

    render_itinerary_timeline(schedule)