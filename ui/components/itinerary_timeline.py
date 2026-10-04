from html import escape

import streamlit as st

from ui.category_content import category_info, resolve_description
from ui.data import has_photo


def _render_drive(item):
    """Small "drive from the previous stop" line above a visit."""
    minutes = item.get("travel_minutes") or 0
    km = item.get("travel_km")
    if not minutes and not km:
        return
    distance = f"{km:.0f} km · " if km else ""
    wait = item.get("wait_minutes") or 0
    wait_text = f" · {wait} min free time before it opens" if wait >= 20 else ""
    st.markdown(
        f'<div class="timeline-drive">🚗 {distance}about {minutes} min drive{wait_text}</div>',
        unsafe_allow_html=True,
    )


def _render_lunch(item):
    st.markdown(
        f'<div class="timeline-break">🍽️ {item.get("start_time", "")} - {item.get("end_time", "")}'
        " &nbsp;Lunch break</div>",
        unsafe_allow_html=True,
    )


def render_itinerary_timeline(schedule, entries=None):
    """Visits (and, when ``entries`` is given, drives and lunch breaks)."""
    items = entries if entries else schedule
    if not items:
        st.info("No itinerary schedule available.")
        return

    for item in items:
        if item.get("kind") == "lunch":
            _render_lunch(item)
            continue
        _render_drive(item)
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

        start_badge = ' <span class="timeline-start">Start of trip</span>' if item.get("is_start") else ""
        note = str(item.get("note") or "")
        timing_note = f'<div class="timeline-note">🕒 {escape(note)}</div>' if note else ""

        st.markdown(
            f"""
            <div class="timeline-item reveal"><div class="timeline-row"><div class="timeline-text">
                <div class="timeline-time">
                    {start_time} - {end_time}{start_badge}
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
                </div>{timing_note}
            </div>{photo_html}</div></div>
            """,
            unsafe_allow_html=True,
        )


def render_day_timeline(
    day_number,
    schedule,
    entries=None,
    drive_km=None,
):
    stops = len(schedule or [])
    summary = f"{stops} stop{'s' if stops != 1 else ''}"
    if drive_km:
        summary += f" · about {float(drive_km):.0f} km driving"
    st.markdown(
        f"""
        <div class="section-title">
            Day {day_number}
        </div>
        <div class="timeline-day-summary">{summary}</div>
        """,
        unsafe_allow_html=True,
    )

    render_itinerary_timeline(schedule, entries=entries)