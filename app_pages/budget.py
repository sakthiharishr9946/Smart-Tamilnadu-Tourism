from html import escape

import streamlit as st

from database.queries import get_all_places, get_districts
from services.ai.insights import generate_budget_notes
from services.budget.calculator import calculate_total_budget
from services.budget.cost_rules import get_budget_rules
from services.nearby.distance import calculate_distance
from ui.components.budget_card import render_budget_card
from ui.components.page_hero import render_page_hero


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


def _searchable_place_select(label, places, key):
    ids = [int(p["place_id"]) for p in places if p.get("place_id") is not None]
    if not ids:
        return None
    selected_id = st.selectbox(
        label,
        ids,
        key=key,
        format_func=lambda place_id: _place_label(_place_map(places)[place_id]),
    )
    return _place_map(places).get(selected_id)


def _nearby_places(reference, places, radius_km):
    if not reference:
        return []
    lat = reference.get("latitude")
    lon = reference.get("longitude")
    if lat is None or lon is None:
        return []

    result = []
    for place in places:
        if place.get("place_id") == reference.get("place_id"):
            continue
        distance = calculate_distance(lat, lon, place.get("latitude"), place.get("longitude"))
        if distance is not None and distance <= radius_km:
            item = dict(place)
            item["distance_km"] = round(distance, 2)
            result.append(item)
    result.sort(key=lambda p: (float(p.get("distance_km", 9999)), -float(p.get("rating", 0) or 0)))
    return result


def _route_distance(places, starting_place=None):
    route = []
    if starting_place:
        route.append(starting_place)
    route.extend(places)

    total = 0.0
    for first, second in zip(route, route[1:]):
        distance = calculate_distance(
            first.get("latitude"), first.get("longitude"),
            second.get("latitude"), second.get("longitude"),
        )
        if distance is not None:
            total += distance
    return round(total, 2)


def _place_multiselect(label, places, key, default=None):
    options = [int(p["place_id"]) for p in places if p.get("place_id") is not None]
    place_lookup = _place_map(places)
    default_ids = [int(p["place_id"]) for p in (default or []) if p.get("place_id") is not None]
    selected_ids = st.multiselect(
        label,
        options,
        default=[x for x in default_ids if x in options],
        key=key,
        format_func=lambda place_id: _place_label(place_lookup[place_id]),
    )
    return [place_lookup[x] for x in selected_ids]


def _common_inputs():
    col1, col2, col3 = st.columns(3)
    with col1:
        travelers = st.number_input("Number of Travelers", min_value=1, max_value=20, value=2, step=1)
    with col2:
        days = st.number_input("Number of Days", min_value=1, max_value=30, value=3, step=1)
    with col3:
        budget_level = st.selectbox("Budget Level", ["budget", "standard", "premium"], index=1)
    return int(travelers), int(days), budget_level


def _calculate_and_store(selected_places, travelers, days, budget_level, starting_place=None):
    nights = max(0, days - 1)
    distance_km = _route_distance(selected_places, starting_place)
    rules = get_budget_rules(budget_level)
    budget = calculate_total_budget(
        distance_km=distance_km,
        travelers=travelers,
        days=days,
        nights=nights,
        places=selected_places,
        transport_cost_per_km=rules["transport"],
        food_cost_per_person_per_day=rules["food_per_person_per_day"],
        accommodation_cost_per_person_per_night=rules["accommodation_per_person_per_night"],
        miscellaneous_cost_per_day=rules["miscellaneous_per_day"],
    )
    st.session_state["travel_budget"] = budget
    st.session_state["budget_calculated_places"] = selected_places
    st.session_state["budget_distance_km"] = distance_km
    with st.spinner("Adding AI budget insights..."):
        st.session_state["budget_ai_notes"] = generate_budget_notes(
            budget, travelers, days, nights, distance_km, budget_level
        )


def render_budget_page():
    render_page_hero(
        "Trip planning",
        "Travel budget planner",
        "Estimate transport, food, stays and entry fees for the places you plan to see.",
        photo_categories=["Beach", "Nature", "Hill"],
    )

    places = [dict(place) for place in get_all_places()]
    if not places:
        st.info("No destinations are available for budget planning.")
        return

    with st.container(key="planner_panel_budget"):
        st.markdown('<div class="panel-title">Your trip details</div>', unsafe_allow_html=True)
        mode = st.radio(
            "How would you like to plan your budget?",
            ["✨ Plan for me", "🗺️ Choose Manually"],
            horizontal=True,
        )

        travelers, days, budget_level = _common_inputs()
        interests = []
        starting_place = None
        selected_places = []

        if mode == "✨ Plan for me":
            st.caption("Choose your district, then where you are starting from. Type in any box to search.")
            interests = st.multiselect(
                "What are you interested in?",
                ["Temple", "Beach", "Hill", "Waterfall", "Wildlife", "Heritage", "Nature", "Historical", "Cultural", "Adventure"],
                key="budget_plan_interests",
            )
            districts = _unique([row["district"] for row in get_districts()])
            district = st.selectbox(
                "Your district",
                districts,
                key="budget_plan_district",
            )
            district_places = [
                p for p in places
                if str(p.get("district", "")).casefold() == str(district).casefold()
            ]
            starting_place = _searchable_place_select(
                "Starting from",
                district_places,
                "budget_plan_start",
            )
            radius_km = st.selectbox("Distance from your start", [10, 25, 50, 75, 100], index=2, format_func=lambda x: f"{x} km")
            candidates = _nearby_places(starting_place, places, radius_km)
            if interests:
                wanted = {x.casefold() for x in interests}
                candidates = [p for p in candidates if str(p.get("category_name") or p.get("subcategory") or "").casefold() in wanted or any(x in str(p.get("category_name", "")).casefold() for x in wanted)]
            candidates = candidates[:10]
            selected_places = _place_multiselect(
                "Places to include (change as you like)",
                candidates,
                "budget_plan_places",
                candidates[:5],
            )
            if starting_place:
                st.caption(f"Your transport estimate starts from {_place_label(starting_place)} and follows the selected destinations.")

        else:
            districts = _unique([row["district"] for row in get_districts()])
            district = st.selectbox("District", districts, key="budget_manual_district")
            district_places = [p for p in places if str(p.get("district", "")).casefold() == district.casefold()]
            selected_places = _place_multiselect(
                "Places to visit",
                district_places,
                "budget_manual_places",
            )
            st.caption("Pick from the list; type to search.")

        if st.button("Calculate Budget", type="primary", use_container_width=True):
            if mode != "🗺️ Choose Manually" and not starting_place:
                st.warning("Please select a starting place.")
                return
            if not selected_places:
                st.warning("Please select at least one tourist place to include in the budget.")
                return
            _calculate_and_store(selected_places, travelers, days, budget_level, starting_place)

    budget = st.session_state.get("travel_budget")
    if not budget:
        return

    st.markdown('<div class="section-title">Estimated Trip Budget</div>', unsafe_allow_html=True)
    render_budget_card(budget)

    distance_km = st.session_state.get("budget_distance_km", 0.0)
    st.caption(f"Estimated travel distance used for calculation: {distance_km:.1f} km")

    ai_notes = st.session_state.get("budget_ai_notes")
    if ai_notes:
        st.markdown(
            f'<div class="info-card"><strong>🤖 AI Budget Insights</strong><p>{escape(ai_notes)}</p></div>',
            unsafe_allow_html=True,
        )


if __name__ == "__main__":
    render_budget_page()
