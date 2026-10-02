import random

import streamlit as st
from geopy.geocoders import Nominatim

from database.queries import get_all_places, get_districts
from services.nearby.distance import calculate_distance
from services.recommendation.scoring import calculate_recommendation_score
from services.recommendation.interest_matching import match_user_interests
from services.recommendation.rating_confidence import add_rating_confidence_to_places
from services.recommendation.popularity import add_popularity_to_places
from services.status.place_status import add_status_to_places
from ui.components.page_hero import render_page_hero
from ui.components.ranked_list import render_ranked_list


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


def _resolve_coordinates(place):
    """Resolve missing coordinates for the selected starting place without creating data."""
    if not place:
        return place
    try:
        lat = float(place.get("latitude"))
        lon = float(place.get("longitude"))
        if -90 <= lat <= 90 and -180 <= lon <= 180:
            return place
    except (TypeError, ValueError):
        pass

    cache = st.session_state.setdefault("recommendation_geocode_cache", {})
    cache_key = "|".join(
        str(place.get(key) or "").strip()
        for key in ("place_name", "city_town", "district")
    )
    if cache_key in cache:
        result = dict(place)
        result.update(cache[cache_key])
        return result

    query_parts = [
        place.get("place_name"),
        place.get("city_town"),
        place.get("district"),
        "Tamil Nadu",
        "India",
    ]
    query = ", ".join(str(x).strip() for x in query_parts if x and str(x).strip())
    try:
        geocoder = Nominatim(user_agent="smart-tamilnadu-tourism-recommendations")
        location = geocoder.geocode(query, timeout=5)
    except Exception:
        location = None

    if location is None:
        cache[cache_key] = {}
        return place

    coords = {"latitude": float(location.latitude), "longitude": float(location.longitude)}
    cache[cache_key] = coords
    result = dict(place)
    result.update(coords)
    return result


def _nearby_places(reference, places, radius_km):
    if not reference:
        return []
    reference = _resolve_coordinates(reference)
    if reference.get("latitude") is None or reference.get("longitude") is None:
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


def _rank(places, interests):
    places = add_status_to_places(
        add_rating_confidence_to_places(add_popularity_to_places(places))
    )
    matched_places = match_user_interests(places, interests)
    scored_places = []
    for place in matched_places:
        place_data = dict(place)
        try:
            score = calculate_recommendation_score(place_data)
        except Exception:
            score = float(place_data.get("rating", 0) or 0)
        place_data["recommendation_score"] = score
        scored_places.append(place_data)

    session_seed = st.session_state.setdefault(
        "recommendation_shuffle_seed", random.randint(0, 1_000_000)
    )
    tie_breaker = random.Random(session_seed)
    tie_values = {item.get("place_id"): tie_breaker.random() for item in scored_places}
    scored_places.sort(
        key=lambda item: (
            item.get("recommendation_score", 0),
            -float(item.get("distance_km", 0) or 0),
            tie_values.get(item.get("place_id"), 0),
        ),
        reverse=True,
    )
    return scored_places


def render_recommendations_page():
    render_page_hero(
        "Curated for you",
        "Recommended for you",
        "Tell us where you are and what you enjoy; we rank the places worth the trip.",
        photo_categories=["Hill", "Waterfall", "Wildlife"],
    )

    places = [dict(place) for place in get_all_places()]
    if not places:
        st.info("No destinations are available for recommendations.")
        return

    with st.container(key="planner_panel_recommendations"):
        st.markdown('<div class="panel-title">Find places for you</div>', unsafe_allow_html=True)
        mode = st.radio(
            "How would you like to discover places?",
            ["✨ Recommend for me", "🗺️ Choose by District"],
            horizontal=True,
        )
        interests = st.multiselect("What are you interested in?", INTERESTS, key="recommendation_interests")
        candidates = places

        if mode == "✨ Recommend for me":
            st.caption("Choose your district, then where you are starting from. Type in any box to search.")
            districts = _unique([row["district"] for row in get_districts()])
            district = st.selectbox(
                "Your district",
                districts,
                key="recommendation_plan_district",
            )
            district_places = [
                p for p in places
                if str(p.get("district", "")).casefold() == str(district).casefold()
            ]
            starting_place = _place_select(
                "Starting from",
                district_places,
                "recommendation_plan_start",
            )
            radius = st.selectbox(
                "Distance from your start",
                [10, 25, 50, 75, 100],
                index=2,
                format_func=lambda x: f"{x} km",
                key="recommendation_plan_radius",
            )
            if starting_place:
                nearby = _nearby_places(starting_place, places, radius)
                # Hard safety gate: recommendation candidates may NEVER exceed the
                # user-selected radius, even if later ranking/scoring code changes.
                candidates = [
                    item for item in nearby
                    if item.get("distance_km") is not None
                    and float(item["distance_km"]) <= float(radius) + 1e-9
                ]
                if candidates:
                    st.caption(
                        f"Showing only destinations within {radius} km of {_place_label(starting_place)}."
                    )
                else:
                    candidates = []
                    st.warning(
                        f"No tourist destinations with usable location data were found within {radius} km of {_place_label(starting_place)}. "
                        "No destinations outside the selected radius are shown."
                    )

        else:
            districts = _unique([row["district"] for row in get_districts()])
            district = st.selectbox("District", ["All Tamil Nadu"] + districts, key="recommendation_district")
            if district != "All Tamil Nadu":
                candidates = [p for p in places if str(p.get("district", "")).casefold() == district.casefold()]
                st.caption(f"Showing tourist places in {district} ({len(candidates)} places).")

    candidates = _filter_interests(candidates, interests)
    ranked = _rank(candidates, interests)
    # District mode is a discovery/catalogue view: show every matching place,
    # not only the first ten. Starting-place mode remains a ranked nearby view.
    recommended_places = ranked if mode == "🗺️ Choose by District" else ranked[:10]

    section_title = "Tourist Places in the Selected District" if mode == "🗺️ Choose by District" else "Top Recommendations"
    st.markdown(f'<div class="section-title">{section_title}</div>', unsafe_allow_html=True)
    if not recommended_places:
        if mode == "✨ Recommend for me" and starting_place:
            st.info(
                "No recommendations match the selected interests within the selected radius. "
                "Try a larger radius or clear some interests."
            )
        else:
            st.info("No recommendations are available for the selected options.")
        return
    render_ranked_list(recommended_places)


if __name__ == "__main__":
    render_recommendations_page()
