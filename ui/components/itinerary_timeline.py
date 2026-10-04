from html import escape

import streamlit as st

from ui.category_content import resolve_description
from ui.data import has_photo


def _duration_text(minutes, about=True):
    """75 -> "about 1 hr 15 min", 150 -> "about 2 hrs 30 min"."""
    minutes = int(minutes or 0)
    hours, rest = divmod(minutes, 60)
    unit = "hr" if hours == 1 else "hrs"
    if hours and rest:
        text = f"{hours} {unit} {rest} min"
    elif hours:
        text = f"{hours} {unit}"
    else:
        text = f"{rest} min"
    return f"about {text}" if about else text


def _render_drive(item):
    """Small "drive from the previous stop" line above a visit."""
    minutes = item.get("travel_minutes") or 0
    km = item.get("travel_km")
    if not minutes and not km:
        return
    distance = f" ({km:.0f} km)" if km else ""
    st.markdown(
        f'<div class="timeline-drive">{escape(f"🚗 Drive {_duration_text(minutes)}{distance}")}</div>',
        unsafe_allow_html=True,
    )


def _render_wait(item):
    """Lunch and free time between arriving and the place opening (temples reopen at 4 pm)."""
    if item.get("lunch_before"):
        _render_lunch(item["lunch_before"])
    if (item.get("wait_minutes") or 0) >= 20:
        st.markdown(
            f'<div class="timeline-drive">☕ Free time until {escape(str(item.get("start_time", "")))} '
            "– rest, or explore the area before it opens</div>",
            unsafe_allow_html=True,
        )


def _render_lunch(item):
    st.markdown(
        f'<div class="timeline-break">🍽️ {item.get("start_time", "")} – {item.get("end_time", "")}'
        " &nbsp;·&nbsp; Lunch break – a good time to try a local meals place nearby</div>",
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
        _render_wait(item)
        place = item.get("place", {})

        place_name_raw = str(place.get("place_name", "Unknown Place"))
        place_name = escape(place_name_raw)

        start_time = item.get("start_time", "")
        end_time = item.get("end_time", "")
        duration = item.get("duration_minutes", 0)

        city = place.get("city_town")
        district_raw = str(place.get("district") or "Tamil Nadu")
        location_raw = f"{city}, {district_raw}" if city and city.casefold() != district_raw.casefold() else district_raw
        location = escape(location_raw.title() if location_raw.islower() else location_raw)

        category = escape(str(place.get("category_name") or "Tourist Attraction"))

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

        entry_fee = place.get("entry_fee")
        fee_text = f"Entry ₹{entry_fee:g}" if entry_fee else "Usually free to enter"

        start_badge = ' <span class="timeline-start">You start here</span>' if item.get("is_start") else ""
        note = str(item.get("note") or "")
        timing_note = f'<div class="timeline-note">🕒 {escape(note)}</div>' if note else ""

        st.markdown(
            f"""
            <div class="timeline-item reveal"><div class="timeline-row"><div class="timeline-text">
                <div class="timeline-time">
                    {start_time} – {end_time}{start_badge}
                </div>
                <div class="timeline-title">
                    {place_name}
                </div>
                <div class="place-card-location">
                    📍 {location} • {category}
                </div>
                <div class="place-card-description">
                    {description}
                </div>{timing_note}
                <div class="timeline-meta">
                    ⏱ Spend {_duration_text(duration)} here &nbsp;·&nbsp; {fee_text}
                </div>
            </div>{photo_html}</div></div>
            """,
            unsafe_allow_html=True,
        )


def day_summary(schedule, drive_km=None):
    """"An easy day around Chengalpattu · 2 stops · about 58 km on the road"."""
    stops = len(schedule or [])
    pace = "An easy day" if stops <= 2 else ("A well-paced day" if stops <= 4 else "A full day")
    districts = []
    for item in schedule or []:
        district = str((item.get("place") or {}).get("district") or "").strip()
        if district and district not in districts:
            districts.append(district)
    around = f" around {' & '.join(districts[:2])}" if districts else ""
    parts = [f"{pace}{around}", f"{stops} stop{'s' if stops != 1 else ''}"]
    if drive_km:
        parts.append(f"about {float(drive_km):.0f} km on the road")
    return " · ".join(parts)


def render_day_timeline(
    day_number,
    schedule,
    entries=None,
    drive_km=None,
):
    st.markdown(
        f"""
        <div class="section-title">
            Day {day_number}
        </div>
        <div class="timeline-day-summary">{escape(day_summary(schedule, drive_km))}</div>
        """,
        unsafe_allow_html=True,
    )

    render_itinerary_timeline(schedule, entries=entries)
