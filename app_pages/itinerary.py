from datetime import time
from html import escape

import streamlit as st

from database.queries import get_all_places
from services.ai.insights import (
    generate_budget_notes,
    generate_itinerary_notes,
)
from services.budget.calculator import calculate_total_budget
from services.budget.cost_rules import get_budget_rules
from services.itinerary.generator import generate_itinerary
from services.nearby.distance import calculate_distance
from services.recommendation.popularity import (
    add_popularity_to_places,
)
from services.recommendation.rating_confidence import (
    add_rating_confidence_to_places,
)
from ui.components.budget_card import render_budget_card
from ui.components.itinerary_timeline import render_day_timeline
from ui.components.page_hero import render_page_hero


# ============================================================
# CONSTANTS
# ============================================================

INTERESTS = [
    "Temple",
    "Beach",
    "Hill",
    "Waterfall",
    "Wildlife",
    "Heritage",
    "Nature",
    "Historical",
    "Cultural",
    "Adventure",
]

BUDGET_LEVELS = [
    "budget",
    "standard",
    "premium",
]

CURRENCY_RATES = {
    "₹ INR": {
        "symbol": "₹",
        "rate": 1.0,
        "code": "INR",
    },
    "$ USD": {
        "symbol": "$",
        "rate": 1 / 83.0,
        "code": "USD",
    },
    "€ EUR": {
        "symbol": "€",
        "rate": 1 / 90.0,
        "code": "EUR",
    },
    "£ GBP": {
        "symbol": "£",
        "rate": 1 / 105.0,
        "code": "GBP",
    },
    "¥ JPY": {
        "symbol": "¥",
        "rate": 1 / 0.56,
        "code": "JPY",
    },
    "د.إ AED": {
        "symbol": "د.إ ",
        "rate": 1 / 22.6,
        "code": "AED",
    },
}


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def _unique(values):
    return sorted(
        {
            str(value).strip()
            for value in values
            if value is not None
            and str(value).strip()
        }
    )


def _place_label(place):
    place_name = str(
        place.get("place_name")
        or "Unknown Place"
    ).strip()

    city = str(
        place.get("city_town")
        or place.get("city")
        or ""
    ).strip()

    if (
        city
        and city.casefold()
        != place_name.casefold()
    ):
        return f"{place_name} - {city}"

    return place_name


def _place_map(places):
    result = {}

    for place in places:
        place_id = place.get("place_id")

        if place_id is None:
            continue

        try:
            result[int(place_id)] = place
        except (
            TypeError,
            ValueError,
        ):
            continue

    return result


def _place_select(
    label,
    places,
    key,
):
    lookup = _place_map(places)

    if not lookup:
        return None

    selected_id = st.selectbox(
        label,
        list(lookup.keys()),
        key=key,
        format_func=lambda place_id: _place_label(
            lookup[place_id]
        ),
    )

    return lookup.get(selected_id)


def _place_multiselect(
    label,
    places,
    key,
):
    lookup = _place_map(places)

    if not lookup:
        return []

    selected_ids = st.multiselect(
        label,
        list(lookup.keys()),
        key=key,
        format_func=lambda place_id: _place_label(
            lookup[place_id]
        ),
    )

    return [
        lookup[place_id]
        for place_id in selected_ids
    ]


def _filter_by_district(
    places,
    district,
):
    if not district:
        return list(places)

    district = str(
        district
    ).strip().casefold()

    filtered = [
        place
        for place in places
        if str(
            place.get("district")
            or ""
        ).strip().casefold()
        == district
    ]

    # If no matching district is found,
    # don't destroy the candidate list.
    return filtered or list(places)


def _filter_by_interests(
    places,
    interests,
):
    if not interests:
        return list(places)

    wanted = {
        str(value).strip().casefold()
        for value in interests
    }

    result = []

    for place in places:

        category = str(
            place.get("category_name")
            or place.get("category")
            or ""
        ).casefold()

        subcategory = str(
            place.get("subcategory")
            or ""
        ).casefold()

        combined = (
            f"{category} {subcategory}"
        )

        if any(
            interest in combined
            for interest in wanted
        ):
            result.append(place)

    return result


def _add_distances(
    places,
    start_place,
):
    if not start_place:
        return list(places)

    start_lat = start_place.get(
        "latitude"
    )
    start_lon = start_place.get(
        "longitude"
    )

    if (
        start_lat is None
        or start_lon is None
    ):
        return list(places)

    result = []

    for place in places:

        if (
            place.get("place_id")
            == start_place.get("place_id")
        ):
            continue

        try:
            distance = calculate_distance(
                start_lat,
                start_lon,
                place.get("latitude"),
                place.get("longitude"),
            )
        except Exception:
            distance = None

        item = dict(place)

        if distance is not None:
            item["distance_km"] = round(
                float(distance),
                2,
            )

        result.append(item)

    return result


def _rank_places(places):
    """
    Ranking used by Plan For Me.

    Priority:
    1. Rating
    2. Popularity
    3. Distance
    """

    if not places:
        return []

    try:
        ranked = add_popularity_to_places(
            [dict(place) for place in places]
        )
    except Exception:
        ranked = [
            dict(place)
            for place in places
        ]

    try:
        ranked = add_rating_confidence_to_places(
            ranked
        )
    except Exception:
        pass

    def get_number(
        place,
        *keys,
        default=0.0,
    ):
        for key in keys:
            value = place.get(key)

            if value is None:
                continue

            try:
                return float(value)
            except (
                TypeError,
                ValueError,
            ):
                continue

        return default

    def score(place):

        rating = get_number(
            place,
            "weighted_rating",
            "rating",
            "average_rating",
            default=0,
        )

        popularity = get_number(
            place,
            "popularity_score",
            "popularity",
            default=0,
        )

        distance = get_number(
            place,
            "distance_km",
            default=9999,
        )

        # Rating is deliberately the strongest factor.
        rating_score = rating * 100

        popularity_score = (
            popularity * 0.20
        )

        # Prefer reasonably close places.
        distance_score = max(
            0,
            20 - distance,
        )

        return (
            rating_score
            + popularity_score
            + distance_score
        )

    ranked.sort(
        key=score,
        reverse=True,
    )

    return ranked


def _select_plan_for_me_places(
    candidates,
    days,
    start_time,
    end_time,
):
    """
    Select a reasonable number of highly-rated places.

    The existing itinerary generator remains responsible
    for the actual day/time scheduling.
    """

    if not candidates:
        return []

    # A reasonable upper limit prevents the generated
    # itinerary from becoming overloaded.
    max_places = max(
        1,
        min(
            len(candidates),
            int(days) * 4,
        ),
    )

    return candidates[:max_places]


def _calculate_route_distance(
    places,
    start_place=None,
):
    route = []

    if start_place:
        route.append(start_place)

    route.extend(places)

    total_distance = 0.0

    for first, second in zip(
        route,
        route[1:],
    ):
        try:
            distance = calculate_distance(
                first.get("latitude"),
                first.get("longitude"),
                second.get("latitude"),
                second.get("longitude"),
            )
        except Exception:
            distance = None

        if distance is not None:
            total_distance += float(
                distance
            )

    return round(
        total_distance,
        2,
    )


def _calculate_budget(
    selected_places,
    travelers,
    days,
    budget_level,
    start_place=None,
):
    nights = max(
        0,
        int(days) - 1,
    )

    distance_km = _calculate_route_distance(
        selected_places,
        start_place,
    )

    rules = get_budget_rules(
        budget_level
    )

    budget = calculate_total_budget(
        distance_km=distance_km,
        travelers=int(travelers),
        days=int(days),
        nights=nights,
        places=selected_places,
        transport_cost_per_km=rules[
            "transport"
        ],
        food_cost_per_person_per_day=rules[
            "food_per_person_per_day"
        ],
        accommodation_cost_per_person_per_night=rules[
            "accommodation_per_person_per_night"
        ],
        miscellaneous_cost_per_day=rules[
            "miscellaneous_per_day"
        ],
    )

    return budget, distance_km


def _clear_generated_results():
    """
    Clear only generated-result state.

    IMPORTANT:
    Do NOT clear widget keys here.
    """

    generated_keys = [
        "generated_itinerary",
        "itinerary_ai_notes",
        "travel_budget",
        "budget_ai_notes",
        "budget_distance_km",
        "budget_calculated_places",
        "generated_trip_days",
        "generated_trip_travelers",
        "generated_trip_budget_level",
        "generated_trip_start_place",
        "generated_trip_mode",
    ]

    for key in generated_keys:
        st.session_state.pop(
            key,
            None,
        )


def _run_itinerary_generation(
    selected_places,
    days,
    start_time,
    end_time,
    travelers,
    budget_level,
    starting_place,
    mode,
):
    """
    Generate itinerary and budget.

    All generated values use separate session-state
    keys so they never conflict with Streamlit widgets.
    """

    try:
        itinerary = generate_itinerary(
            selected_places,
            days=int(days),
            start_time=start_time.strftime(
                "%H:%M"
            ),
            end_time=end_time.strftime(
                "%H:%M"
            ),
        )

    except Exception as error:
        st.error(
            f"Unable to generate itinerary: {error}"
        )
        return False

    if not itinerary:
        st.warning(
            "Unable to create an itinerary "
            "with the selected places."
        )
        return False

    # --------------------------------------------------------
    # GENERATED ITINERARY
    # --------------------------------------------------------

    st.session_state[
        "generated_itinerary"
    ] = itinerary

    st.session_state[
        "generated_trip_days"
    ] = int(days)

    st.session_state[
        "generated_trip_travelers"
    ] = int(travelers)

    st.session_state[
        "generated_trip_budget_level"
    ] = budget_level

    st.session_state[
        "generated_trip_start_place"
    ] = starting_place

    st.session_state[
        "generated_trip_mode"
    ] = mode

    st.session_state[
        "generated_trip_selected_count"
    ] = len(selected_places)

    # --------------------------------------------------------
    # AI NOTES
    # --------------------------------------------------------

    try:
        st.session_state[
            "itinerary_ai_notes"
        ] = generate_itinerary_notes(
            itinerary
        )
    except Exception:
        st.session_state[
            "itinerary_ai_notes"
        ] = ""

    # --------------------------------------------------------
    # BUDGET
    # --------------------------------------------------------

    try:
        budget, distance_km = (
            _calculate_budget(
                selected_places,
                travelers,
                days,
                budget_level,
                starting_place,
            )
        )

        st.session_state[
            "travel_budget"
        ] = budget

        st.session_state[
            "budget_distance_km"
        ] = distance_km

        st.session_state[
            "budget_calculated_places"
        ] = selected_places

    except Exception as error:
        st.warning(
            f"Budget could not be calculated: {error}"
        )

        st.session_state[
            "travel_budget"
        ] = None

        st.session_state[
            "budget_distance_km"
        ] = 0.0

    # --------------------------------------------------------
    # BUDGET AI NOTES
    # --------------------------------------------------------

    try:
        if st.session_state.get(
            "travel_budget"
        ):

            st.session_state[
                "budget_ai_notes"
            ] = generate_budget_notes(
                st.session_state[
                    "travel_budget"
                ],
                int(travelers),
                int(days),
                max(
                    0,
                    int(days) - 1,
                ),
                st.session_state.get(
                    "budget_distance_km",
                    0.0,
                ),
                budget_level,
            )

        else:
            st.session_state[
                "budget_ai_notes"
            ] = ""

    except Exception:
        st.session_state[
            "budget_ai_notes"
        ] = ""

    return True


# ============================================================
# MAIN PAGE
# ============================================================

def render_itinerary_page():

    render_page_hero(
        "Trip planning",
        "Plan your itinerary",
        "Choose your places yourself or let Smart Tamilnadu Tourism create a personalized plan for you.",
        photo_categories=[
            "Heritage",
            "Historical",
            "Temple",
        ],
    )

    # --------------------------------------------------------
    # LOAD PLACES
    # --------------------------------------------------------

    try:
        raw_places = get_all_places()
    except Exception as error:
        st.error(
            f"Unable to load tourist places: {error}"
        )
        return

    places = [
        dict(place)
        for place in raw_places
    ]

    if not places:
        st.info(
            "No destinations are available "
            "for itinerary planning."
        )
        return

    # ========================================================
    # PLANNER PANEL
    # ========================================================

    with st.container(
        key="planner_panel_itinerary"
    ):

        st.markdown(
            '<div class="panel-title">'
            "Plan your trip"
            "</div>",
            unsafe_allow_html=True,
        )

        # ----------------------------------------------------
        # PLANNING MODE
        # ----------------------------------------------------

        mode = st.radio(
            "How would you like to plan your itinerary?",
            [
                "🗺️ Plan Manually",
                "✨ Plan For Me",
            ],
            horizontal=True,
            key="itinerary_mode",
        )

        # ----------------------------------------------------
        # TRIP DETAILS
        # ----------------------------------------------------

        st.markdown(
            "### 🧳 Trip Details"
        )

        col1, col2, col3 = st.columns(
            3
        )

        with col1:

            days = st.number_input(
                "Number of Days",
                min_value=1,
                max_value=15,
                value=2,
                step=1,
                key="itinerary_days",
            )

        with col2:

            travelers = st.number_input(
                "Number of Persons",
                min_value=1,
                max_value=50,
                value=2,
                step=1,
                key="itinerary_travelers",
            )

        with col3:

            budget_level = st.selectbox(
                "Budget Category",
                BUDGET_LEVELS,
                index=1,
                format_func=lambda value: (
                    value.title()
                ),
                key="itinerary_budget_level",
            )

        col1, col2 = st.columns(2)

        with col1:

            start_time = st.time_input(
                "Start Time",
                value=time(9, 0),
                key="itinerary_start_time",
            )

        with col2:

            end_time = st.time_input(
                "End Time",
                value=time(19, 0),
                key="itinerary_end_time",
            )

        # ----------------------------------------------------
        # START PLACE
        # ----------------------------------------------------

        st.markdown(
            "### 📍 Starting Location"
        )

        col1, col2 = st.columns(
            [2, 1]
        )

        with col1:

            starting_place = _place_select(
                "Start Place",
                places,
                "itinerary_start_place",
            )

        with col2:

            districts = _unique(
                [
                    place.get("district")
                    for place in places
                ]
            )

            district_options = [
                "Not specified"
            ] + districts

            selected_district = st.selectbox(
                "District (Optional)",
                district_options,
                key="itinerary_district",
            )

        # ----------------------------------------------------
        # AUTOMATIC DISTRICT
        # ----------------------------------------------------

        detected_district = ""

        if starting_place:

            detected_district = str(
                starting_place.get(
                    "district"
                )
                or ""
            ).strip()

        if (
            selected_district
            != "Not specified"
        ):

            effective_district = (
                selected_district
            )

        else:

            effective_district = (
                detected_district
            )

        if detected_district:

            if (
                selected_district
                == "Not specified"
            ):

                st.caption(
                    "District automatically identified "
                    f"from Start Place: **{detected_district}**"
                )

        # ----------------------------------------------------
        # INTERESTS
        # ----------------------------------------------------

        st.markdown(
            "### ❤️ Place Interests"
        )

        interests = st.multiselect(
            "What would you like to explore?",
            INTERESTS,
            key="itinerary_interests",
        )

        # ----------------------------------------------------
        # SELECT PLACES
        # ----------------------------------------------------

        selected_places = []

        if (
            mode
            == "🗺️ Plan Manually"
        ):

            st.markdown(
                "### 📌 Choose Places"
            )

            st.caption(
                "Select the exact tourist places "
                "you want to include."
            )

            candidates = _filter_by_district(
                places,
                effective_district,
            )

            if interests:

                interest_candidates = (
                    _filter_by_interests(
                        candidates,
                        interests,
                    )
                )

                if interest_candidates:
                    candidates = (
                        interest_candidates
                    )

            candidates = _rank_places(
                candidates
            )

            selected_places = (
                _place_multiselect(
                    "Places to Visit",
                    candidates,
                    "itinerary_manual_places",
                )
            )

        else:

            st.markdown(
                "### ✨ Let Us Plan For You"
            )

            st.info(
                "We will select highly-rated places "
                "that match your interests and fit "
                "your selected number of days and "
                "available time."
            )

            candidate_places = (
                _filter_by_district(
                    places,
                    effective_district,
                )
            )

            # Remove the starting place.
            if starting_place:

                candidate_places = [
                    place
                    for place in candidate_places
                    if place.get("place_id")
                    != starting_place.get(
                        "place_id"
                    )
                ]

            # Apply interests.
            if interests:

                candidate_places = (
                    _filter_by_interests(
                        candidate_places,
                        interests,
                    )
                )

            # Add distance.
            candidate_places = (
                _add_distances(
                    candidate_places,
                    starting_place,
                )
            )

            # Rank.
            candidate_places = _rank_places(
                candidate_places
            )

            if candidate_places:

                selected_places = (
                    _select_plan_for_me_places(
                        candidate_places,
                        int(days),
                        start_time,
                        end_time,
                    )
                )

                if selected_places:

                    st.markdown(
                        "#### ⭐ Places selected for you"
                    )

                    for place in selected_places:

                        try:
                            rating = float(
                                place.get(
                                    "rating",
                                    0,
                                )
                                or 0
                            )
                        except (
                            TypeError,
                            ValueError,
                        ):
                            rating = 0.0

                        distance = place.get(
                            "distance_km"
                        )

                        if distance is not None:

                            distance_text = (
                                f" • {float(distance):.1f} km"
                            )

                        else:

                            distance_text = ""

                        st.markdown(
                            f"- **{escape(_place_label(place))}** "
                            f"⭐ {rating:.1f}"
                            f"{distance_text}"
                        )

                    st.caption(
                        "Places are prioritized by rating, "
                        "then popularity and distance."
                    )

            else:

                st.warning(
                    "No places match the selected "
                    "interests and district."
                )

        # ----------------------------------------------------
        # GENERATE BUTTON
        # ----------------------------------------------------

        if (
            mode
            == "🗺️ Plan Manually"
        ):

            button_label = (
                "🗺️ Plan Itinerary"
            )

        else:

            button_label = (
                "✨ Plan For Me"
            )

        if st.button(
            button_label,
            type="primary",
            use_container_width=True,
            key="generate_itinerary_button",
        ):

            # Validate time.
            if start_time >= end_time:

                st.warning(
                    "End Time must be later "
                    "than Start Time."
                )

                return

            # Validate start place.
            if not starting_place:

                st.warning(
                    "Please select a Start Place."
                )

                return

            # Validate destinations.
            if not selected_places:

                if (
                    mode
                    == "🗺️ Plan Manually"
                ):

                    st.warning(
                        "Please select at least "
                        "one tourist place."
                    )

                else:

                    st.warning(
                        "No suitable places were found "
                        "for your selected preferences."
                    )

                return

            # ------------------------------------------------
            # IMPORTANT:
            # Only generated state is cleared.
            # Widget state is NOT touched.
            # ------------------------------------------------

            _clear_generated_results()

            success = (
                _run_itinerary_generation(
                    selected_places=selected_places,
                    days=days,
                    start_time=start_time,
                    end_time=end_time,
                    travelers=travelers,
                    budget_level=budget_level,
                    starting_place=starting_place,
                    mode=mode,
                )
            )

            if success:

                st.success(
                    "Your itinerary has been created successfully."
                )

    # ========================================================
    # GENERATED ITINERARY
    # ========================================================

    itinerary = st.session_state.get(
        "generated_itinerary"
    )

    if not itinerary:
        return

    st.markdown(
        '<div class="section-title">'
        "🗓️ Your Travel Plan"
        "</div>",
        unsafe_allow_html=True,
    )

    # --------------------------------------------------------
    # SUMMARY
    # --------------------------------------------------------

    generated_mode = st.session_state.get(
        "generated_trip_mode",
        "🗺️ Plan Manually",
    )

    generated_days = st.session_state.get(
        "generated_trip_days",
        1,
    )

    generated_travelers = (
        st.session_state.get(
            "generated_trip_travelers",
            1,
        )
    )

    generated_budget_level = (
        st.session_state.get(
            "generated_trip_budget_level",
            "standard",
        )
    )

    generated_count = (
        st.session_state.get(
            "generated_trip_selected_count",
            0,
        )
    )

    summary_col1, summary_col2, summary_col3, summary_col4 = (
        st.columns(4)
    )

    with summary_col1:
        st.metric(
            "Planning Mode",
            (
                "Plan For Me"
                if "Plan For Me"
                in generated_mode
                else "Manual"
            ),
        )

    with summary_col2:
        st.metric(
            "Days",
            generated_days,
        )

    with summary_col3:
        st.metric(
            "Persons",
            generated_travelers,
        )

    with summary_col4:
        st.metric(
            "Places",
            generated_count,
        )

    # --------------------------------------------------------
    # AI NOTES
    # --------------------------------------------------------

    ai_notes = st.session_state.get(
        "itinerary_ai_notes",
        "",
    )

    if ai_notes:

        st.markdown(
            '<div class="info-card">'
            "<strong>🤖 AI Trip Notes</strong>"
            f"<p>{escape(str(ai_notes))}</p>"
            "</div>",
            unsafe_allow_html=True,
        )

    # --------------------------------------------------------
    # REMAINING PLACES
    # --------------------------------------------------------

    remaining = []

    if itinerary:

        remaining = itinerary[-1].get(
            "remaining_places",
            [],
        )

    scheduled_count = sum(
        len(
            day.get(
                "schedule",
                [],
            )
        )
        for day in itinerary
    )

    if remaining:

        st.warning(
            f"{scheduled_count} of "
            f"{generated_count} selected places "
            f"fit within the available time."
        )

        st.markdown(
            "**Places not included in the schedule:**"
        )

        st.write(
            ", ".join(
                place.get(
                    "place_name",
                    "Unknown Place",
                )
                for place in remaining
            )
        )

    else:

        st.success(
            "All selected places fit within "
            "your available travel time."
        )

    # --------------------------------------------------------
    # DAY-BY-DAY ITINERARY
    # --------------------------------------------------------

    for day in itinerary:

        render_day_timeline(
            day.get(
                "day",
                1,
            ),
            day.get(
                "schedule",
                [],
            ),
        )

    # ========================================================
    # BUDGET
    # ========================================================

    st.markdown(
        '<div class="section-title">'
        "💰 Estimated Trip Budget"
        "</div>",
        unsafe_allow_html=True,
    )

    budget = st.session_state.get(
        "travel_budget"
    )

    if not budget:

        st.info(
            "Budget information is not available."
        )

        return

    # IMPORTANT:
    # Currency selector has its own widget key.
    # It is never manually modified.
    currency = st.selectbox(
        "Currency",
        list(CURRENCY_RATES.keys()),
        key="itinerary_currency",
    )

    render_budget_card(
        budget,
        currency=currency,
        currency_rates=CURRENCY_RATES,
    )

    distance_km = st.session_state.get(
        "budget_distance_km",
        0.0,
    )

    st.caption(
        f"Estimated travel distance: "
        f"{float(distance_km):.1f} km • "
        f"Persons: {generated_travelers} • "
        f"Budget category: "
        f"{str(generated_budget_level).title()}"
    )

    # --------------------------------------------------------
    # BUDGET AI NOTES
    # --------------------------------------------------------

    budget_ai_notes = (
        st.session_state.get(
            "budget_ai_notes",
            "",
        )
    )

    if budget_ai_notes:

        st.markdown(
            '<div class="info-card">'
            "<strong>🤖 AI Budget Insights</strong>"
            f"<p>{escape(str(budget_ai_notes))}</p>"
            "</div>",
            unsafe_allow_html=True,
        )


if __name__ == "__main__":
    render_itinerary_page()