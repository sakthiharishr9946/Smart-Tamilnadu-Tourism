from datetime import time
from html import escape

import streamlit as st

from database.queries import get_all_places, get_districts
from services.ai.insights import generate_itinerary_notes
from services.itinerary.generator import generate_itinerary
from services.recommendation.rating_confidence import add_rating_confidence_to_places
from services.recommendation.popularity import add_popularity_to_places
from services.nearby.distance import calculate_distance
from ui.components.itinerary_timeline import render_day_timeline
from ui.components.page_hero import render_page_hero


INTERESTS = [
    "Temple", "Beach", "Hill", "Waterfall", "Wildlife", "Heritage",
    "Nature", "Historical", "Cultural", "Adventure",
]


def _unique(values):
    return sorted({str(v).strip() for v in values if v and str(v).strip()})


def _place_label(place):
    # Show place + city/town only. The district is already selected separately.
    place_name = str(place.get("place_name") or "Unknown Place").strip()
    city = str(place.get("city_town") or place.get("city") or "").strip()
    if city and city.casefold() != place_name.casefold():
        return f"{place_name} - {city}"
    return place_name


def _place_map(places):
    return {int(p["place_id"]): p for p in places if p.get("place_id") is not None}


def _place_select(label, places, key):
    lookup = _place_map(places)
    if not lookup:
        return None
    selected_id = st.selectbox(
        label,
        list(lookup),
        key=key,
        format_func=lambda place_id: _place_label(lookup[place_id]),
    )
    return lookup.get(selected_id)


def _nearby_places(reference, places, radius_km):
    if not reference or reference.get("latitude") is None or reference.get("longitude") is None:
        return []
    result = []
    for place in places:
        if place.get("place_id") == reference.get("place_id"):
            continue
        distance = calculate_distance(
            reference.get("latitude"), reference.get("longitude"),
            place.get("latitude"), place.get("longitude"),
        )
        if distance is not None and distance <= radius_km:
            item = dict(place)
            item["distance_km"] = distance
            result.append(item)
    result.sort(key=lambda p: (float(p.get("distance_km", 9999)), -float(p.get("rating", 0) or 0)))
    return result


def _filter_interests(places, interests):
    if not interests:
        return places
    wanted = {x.casefold() for x in interests}
    return [
        p for p in places
        if any(x in str(p.get("category_name", "")).casefold() for x in wanted)
        or any(x in str(p.get("subcategory", "")).casefold() for x in wanted)
    ]


def _rank_places(places):
    ranked = add_rating_confidence_to_places(add_popularity_to_places(places))
    ranked.sort(
        key=lambda p: (
            float(p.get("weighted_rating", p.get("rating", 0)) or 0),
            float(p.get("popularity_score", 0) or 0),
            -float(p.get("distance_km", 0) or 0),
        ),
        reverse=True,
    )
    return ranked


def _place_multiselect(label, places, key, default=None):
    lookup = _place_map(places)
    if not lookup:
        return []
    default_ids = [int(p["place_id"]) for p in (default or []) if p.get("place_id") in lookup]
    selected_ids = st.multiselect(
        label,
        list(lookup),
        default=default_ids,
        key=key,
        format_func=lambda place_id: _place_label(lookup[place_id]),
    )
    return [lookup[x] for x in selected_ids]


def render_itinerary_page():
    render_page_hero(
        "Trip planning",
        "Plan your itinerary",
        "Pick a start, the places you want and your hours; we build a day-by-day plan.",
        photo_categories=["Heritage", "Historical", "Temple"],
    )

    places = [dict(place) for place in get_all_places()]
    if not places:
        st.info("No destinations are available for itinerary planning.")
        return

    with st.container(key="planner_panel_itinerary"):
        st.markdown('<div class="panel-title">Build your trip</div>', unsafe_allow_html=True)
        mode = st.radio(
            "How would you like to plan your itinerary?",
            ["✨ Plan for me", "🗺️ Choose Manually"],
            horizontal=True,
        )
        interests = st.multiselect("What are you interested in?", INTERESTS, key="itinerary_interests")
        selected_places = []
        starting_place = None

        if mode == "✨ Plan for me":
            st.caption("Choose your district, then where you are starting from. Type in any box to search.")
            districts = _unique([row["district"] for row in get_districts()])
            district = st.selectbox(
                "Your district",
                districts,
                key="itinerary_plan_district",
            )
            district_places = [
                p for p in places
                if str(p.get("district", "")).casefold() == str(district).casefold()
            ]
            starting_place = _place_select(
                "Starting from",
                district_places,
                "itinerary_plan_start",
            )
            radius = st.selectbox(
                "Distance from your start",
                [10, 25, 50, 75, 100],
                index=2,
                format_func=lambda x: f"{x} km",
                key="itinerary_plan_radius",
            )
            candidates = _nearby_places(starting_place, places, radius)
            candidates = _filter_interests(candidates, interests)
            candidates = _rank_places(candidates)[:15]
            selected_places = _place_multiselect(
                "Recommended tourist places (you can change the selection)",
                candidates,
                "itinerary_plan_places",
                candidates[:5],
            )
            if starting_place:
                st.caption(f"Starting from {_place_label(starting_place)}.")

        else:
            districts = _unique([row["district"] for row in get_districts()])
            district = st.selectbox("District", districts, key="itinerary_manual_district")
            district_places = [p for p in places if str(p.get("district", "")).casefold() == district.casefold()]
            location_type = st.selectbox("Search around a", ["City", "Place"], key="itinerary_manual_type")
            candidates = district_places
            if location_type == "City":
                cities = _unique([p.get("city_town") for p in district_places])
                if cities:
                    city = st.selectbox("City", cities, key="itinerary_manual_city")
                    candidates = [p for p in district_places if str(p.get("city_town", "")).casefold() == city.casefold()]
                else:
                    st.warning("No cities are available for the selected district.")
                    return
            else:
                reference = _place_select("Place", district_places, "itinerary_manual_reference")
                if reference:
                    nearby = _nearby_places(reference, district_places, 50)
                    candidates = nearby or district_places
                    if nearby:
                        st.caption(f"Showing tourist places within 50 km of {_place_label(reference)}.")
            candidates = _filter_interests(candidates, interests)
            candidates = _rank_places(candidates)
            selected_places = _place_multiselect("Places to visit", candidates, "itinerary_manual_places")

        col1, col2, col3 = st.columns(3)
        with col1:
            days = st.number_input("Number of days", min_value=1, max_value=15, value=2, step=1)
        with col2:
            start_time = st.time_input("Start time", value=time(9, 0), key="itinerary_start_time")
        with col3:
            end_time = st.time_input("End time", value=time(17, 0), key="itinerary_end_time")

        if st.button("Generate Itinerary", type="primary", use_container_width=True):
            if start_time >= end_time:
                st.warning("End time must be later than start time.")
                return
            if not selected_places:
                st.warning("Please select at least one tourist place.")
                return
            try:
                itinerary = generate_itinerary(
                    selected_places,
                    days=int(days),
                    start_time=start_time.strftime("%H:%M"),
                    end_time=end_time.strftime("%H:%M"),
                )
            except Exception as error:
                st.error(f"Unable to generate itinerary: {error}")
                return
            st.session_state["generated_itinerary"] = itinerary
            st.session_state["itinerary_selected_count"] = len(selected_places)
            with st.spinner("Adding AI trip notes..."):
                st.session_state["itinerary_ai_notes"] = generate_itinerary_notes(itinerary)

    itinerary = st.session_state.get("generated_itinerary")
    if not itinerary:
        return

    st.markdown('<div class="section-title">Your Travel Plan</div>', unsafe_allow_html=True)
    ai_notes = st.session_state.get("itinerary_ai_notes")
    if ai_notes:
        st.markdown(f'<div class="info-card"><strong>🤖 AI Trip Notes</strong><p>{escape(ai_notes)}</p></div>', unsafe_allow_html=True)

    remaining = itinerary[-1].get("remaining_places", []) if itinerary else []
    scheduled_count = sum(len(day.get("schedule", [])) for day in itinerary)
    if remaining:
        st.warning(
            f"{scheduled_count} of {st.session_state.get('itinerary_selected_count', scheduled_count + len(remaining))} selected places fit within {int(days)} day(s) between {start_time.strftime('%H:%M')} and {end_time.strftime('%H:%M')}."
        )
        st.markdown("**Places remaining — consider extending your trip:**")
        st.write(", ".join(p.get("place_name", "Unknown Place") for p in remaining))
    else:
        st.success("All selected places fit within the selected days and daily time window.")

    for day in itinerary:
        render_day_timeline(day.get("day", 1), day.get("schedule", []))


if __name__ == "__main__":
    render_itinerary_page()
