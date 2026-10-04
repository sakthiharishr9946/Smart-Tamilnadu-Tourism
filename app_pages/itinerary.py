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
from services.itinerary.planner import plan_trip
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


# "Plan For Me" looks this far around the start place (km, straight line),
# a little further for each extra day.
PLAN_FOR_ME_RADIUS_KM = 40
PLAN_FOR_ME_EXTRA_KM_PER_DAY = 25


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


def _place_label(place, show_district=False):
    """"Name — Town, District · Type · 12 km", skipping parts the name already says.

    Showing the district tells apart look-alikes such as Maruthamalai
    (Coimbatore) and Maruthwamalai (Kanyakumari).
    """
    place_name = str(
        place.get("place_name")
        or "Unknown Place"
    ).strip()
    lowered = place_name.casefold()

    where = []
    city = str(place.get("city_town") or place.get("city") or "").strip()
    if city and city.casefold() not in lowered:
        where.append(city.title() if city.islower() else city)
    district = str(place.get("district") or "").strip()
    if show_district and district and district.casefold() not in lowered and \
            district.casefold() not in (w.casefold() for w in where):
        where.append(district)

    label = place_name + (f" — {', '.join(where)}" if where else "")
    if show_district and place.get("category_name"):
        label += f" · {place['category_name']}"
    if place.get("distance_km") is not None:
        label += f" · {float(place['distance_km']):.0f} km"
    return label


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
            lookup[place_id],
            show_district=True,
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
    Pick well-known places near the start, as many as the days can hold.

    ``candidates`` carry ``distance_km`` from the start place. The trip
    planner then decides the days, order and times (and leaves out any
    place that does not fit).
    """

    if not candidates:
        return []

    hours = max(2.0, (end_time.hour * 60 + end_time.minute - start_time.hour * 60 - start_time.minute) / 60)
    # About one stop per two hours (visit + drive), a few spare for the planner.
    wanted = max(2, round(int(days) * hours / 2)) + 2
    radius = PLAN_FOR_ME_RADIUS_KM + PLAN_FOR_ME_EXTRA_KM_PER_DAY * (int(days) - 1)

    # Only places that can go on the map, near enough to reach.
    located = [p for p in candidates if p.get("latitude") is not None and p.get("longitude") is not None]
    nearby = [p for p in located if p.get("distance_km") is None or float(p["distance_km"]) <= radius]

    def score(place):
        popularity = float(place.get("popularity_score") or 0)
        distance = float(place.get("distance_km") or 0)
        return popularity - 0.5 * distance

    ranked = sorted(nearby, key=score, reverse=True)

    # A varied trip: no single kind of place takes more than half the
    # slots, unless that is all the traveller asked for.
    per_kind_limit = max(2, (wanted + 1) // 2)
    chosen, per_kind = [], {}
    for place in ranked:
        kind = place.get("category_name") or "Other"
        if per_kind.get(kind, 0) >= per_kind_limit:
            continue
        chosen.append(place)
        per_kind[kind] = per_kind.get(kind, 0) + 1
        if len(chosen) >= wanted:
            break
    if len(chosen) < wanted:
        chosen += [p for p in ranked if p not in chosen][: wanted - len(chosen)]
    return chosen


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
    distance_km=None,
):
    nights = max(
        0,
        int(days) - 1,
    )

    if distance_km is None:
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
        "generated_unscheduled",
        "generated_total_km",
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
        plan = plan_trip(
            selected_places,
            start_place=starting_place,
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

    # "schedule" (visits only) keeps the AI notes and older views working;
    # "entries" adds lunch breaks for the timeline.
    itinerary = [
        {**day, "schedule": [e for e in day["entries"] if e["kind"] == "visit"]}
        for day in plan["days"]
    ]
    planned_places = [
        entry["place"]
        for day in itinerary
        for entry in day["schedule"]
        if not entry.get("is_start")
    ]
    st.session_state["generated_unscheduled"] = plan["unscheduled"]
    st.session_state["generated_total_km"] = plan["total_km"]

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
    ] = len(planned_places) + (1 if starting_place else 0)

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
                planned_places,
                travelers,
                days,
                budget_level,
                starting_place,
                distance_km=plan["total_km"],
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
        ] = planned_places

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

            # The start place is already the first stop of day 1.
            if starting_place:
                candidates = [
                    place
                    for place in candidates
                    if place.get("place_id") != starting_place.get("place_id")
                ]

            candidates = _rank_places(
                _add_distances(candidates, starting_place)
            )
            # Nearest first when the start is on the map; places without a
            # map location go last.
            if starting_place and starting_place.get("latitude") is not None:
                candidates.sort(
                    key=lambda place: (
                        place.get("distance_km") is None,
                        place.get("distance_km") or 0,
                    )
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
                "We pick well-known places near your start that match "
                "your interests, then plan each day around one area: "
                "temples in the morning or after 4 pm, parks, dams and "
                "waterfalls in daylight, museums at midday."
            )

            # Around the start place by distance, unless a district was
            # chosen explicitly (start places near a border have their
            # nearest sights in the next district).
            candidate_places = (
                _filter_by_district(places, selected_district)
                if selected_district != "Not specified"
                else list(places)
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

                        distance = place.get(
                            "distance_km"
                        )
                        distance_text = (
                            f" • {float(distance):.0f} km from start"
                            if distance is not None
                            else ""
                        )

                        st.markdown(
                            f"- **{escape(str(place.get('place_name') or 'Place'))}** "
                            f"• {escape(str(place.get('category_name') or 'Destination'))}"
                            f"{distance_text}"
                        )

                    st.caption(
                        "Chosen by how well-known each place is and how "
                        "close it is to your start. Places that do not fit "
                        "your days are listed after the plan."
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
                    "Your trip is ready - scroll down to see it."
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
            "Stops",
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

    remaining = st.session_state.get("generated_unscheduled") or []
    mode_is_auto = "Plan For Me" in generated_mode

    if remaining and not mode_is_auto:
        # Manual picks that could not be planned: say why, not just which.
        st.warning(
            f"{'One place' if len(remaining) == 1 else f'{len(remaining)} places'} didn't fit into "
            f"{generated_days} day{'s' if generated_days != 1 else ''} without a long detour or "
            "arriving when it's closed. Add another day, or choose places closer together."
        )
        st.markdown(
            "**Saved for another trip:** "
            + ", ".join(
                escape(str(place.get("place_name", "Unknown Place")))
                for place in remaining
            )
        )
    elif not remaining:
        st.success(
            f"Everything fits nicely into {generated_days} "
            f"day{'s' if generated_days != 1 else ''}."
        )

    total_km = st.session_state.get("generated_total_km")
    if total_km:
        st.caption(
            f"You'll drive about {float(total_km):.0f} km in all. We've timed temples for "
            "the morning or after 4 pm, and parks, dams and waterfalls for daylight."
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
            entries=day.get("entries"),
            drive_km=day.get("drive_km"),
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