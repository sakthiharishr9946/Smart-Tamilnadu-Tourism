import streamlit as st

from database.queries import (
    get_all_categories,
    search_places,
)
from services.data_updates import refresh_tourism_data
from services.location.current_location import clear_current_location, get_current_location, set_current_location
from services.location.geocoding import geocode_location
from services.search.start_search import start_search
from ui.components.map_view import render_map_view
from ui.components.place_grid import render_place_grid
from ui.components.search_bar import render_search_bar
from ui.components.hero_visual import render_hero_3d_showcase
from ui.components.scroll_row import render_scroll_row
from ui.components.category_showcase import render_category_showcase
from ui.data import clear_place_cache, load_places
from ui.components.gps import gps_pending, poll_gps, start_gps_request

# Tiles per category row on the default browse view, and cards in a
# filtered result grid; the full set is always on the map.
ROW_TILES = 15
GRID_LIMIT = 60


def _render_editorial_hero():
    all_places = load_places()
    total_places = len(all_places)
    total_districts = len({place.get("district") for place in all_places if place.get("district")})

    # Text needs ~46ch; giving the card strip the larger share removes the
    # empty band that used to sit between the headline and the cards.
    col_text, col_visual = st.columns([5, 7], gap="medium")

    with col_text:
        st.markdown(
            '<div class="hero-eyebrow reveal">Tamil Nadu &middot; South India</div>'
            '<div class="hero-editorial-title reveal">Explore the<br>South, slowly.</div>'
            '<div class="hero-editorial-rule reveal"></div>'
            '<div class="hero-editorial-subtitle reveal">'
            f"Discover {total_places} destinations across {total_districts} districts "
            "&mdash; temples, coastlines, hill country and wild places, curated for "
            "the way you actually travel."
            "</div>",
            unsafe_allow_html=True,
        )

    with col_visual:
        render_hero_3d_showcase()


def _render_browse_rows(places):
    """One row per category with its most prominent places first."""
    by_category = {}
    for place in places:
        category = str(place.get("category_name") or "Other").strip() or "Other"
        by_category.setdefault(category, []).append(place)

    for category in sorted(by_category, key=lambda name: -len(by_category[name])):
        members = by_category[category]
        render_scroll_row(category, members[:ROW_TILES], subtitle=f"{len(members)} places")


def _gps_label(accuracy):
    try:
        accuracy = float(accuracy)
    except (TypeError, ValueError):
        return "your location"
    if accuracy > 5000:
        # Desktop browsers without GPS locate by IP address / Wi-Fi.
        return f"your approximate location (±{accuracy / 1000:.0f} km)"
    return "your location"


def _run_nearby_search(location, label):
    with st.spinner("Finding destinations near you…"):
        results, context = start_search(location[0], location[1])
    st.session_state["nearby_results"] = results
    st.session_state["nearby_context"] = context
    st.session_state["nearby_label"] = label


def render_explore_page():
    _render_editorial_hero()

    search_query = render_search_bar()

    st.markdown('<div class="ghost-toolbar-label reveal">Find destinations near you</div>', unsafe_allow_html=True)
    col_manual, col_gps, col_refresh = st.columns([4, 1, 1])
    with col_manual:
        location_name = st.text_input(
            "Your location",
            placeholder="Enter a town, city, or district - or press GPS",
            label_visibility="collapsed",
        )
    with col_gps:
        if st.button("📍 GPS", use_container_width=True, help="Use this device's location"):
            start_gps_request()
    with col_refresh:
        refresh_requested = st.button("↻ Refresh", use_container_width=True)

    # GPS: the browser answers on a later run; search as soon as it does.
    gps_location, gps_accuracy, gps_error = poll_gps()
    if gps_error:
        st.warning(gps_error)
    elif gps_location:
        _run_nearby_search(gps_location, _gps_label(gps_accuracy))
    elif gps_pending():
        st.info("📍 Finding your location… allow location access if your browser asks.")

    if refresh_requested:
        with st.spinner("Updating from the public tourism source..."):
            try:
                # OpenStreetMap collection can take a long time on busy public
                # servers; it is refreshed by scripts/refresh_data.py instead and
                # its places stay in the database.
                update = refresh_tourism_data(skip=("osm",))
                clear_place_cache()
                st.success(f"Updated {update['records_updated']} places from {update['source']}.")
                st.rerun()
            except Exception as error:
                st.error(f"Could not update tourism data: {error}")

    if st.button("Start Searching", type="primary", use_container_width=True):
        location = None
        if location_name.strip():
            # A typed place always wins over an earlier GPS fix.
            with st.spinner(f"Finding {location_name.strip()}…"):
                coordinates = geocode_location(location_name)
            if coordinates:
                set_current_location(*coordinates)
                location = coordinates
                label = location_name.strip()
            else:
                st.warning("That location could not be found. Try a more specific Tamil Nadu town or district.")
        else:
            location = get_current_location()
            label = st.session_state.get("nearby_label", "your location")
            if not location:
                st.warning("Press GPS, or enter a town or district, to search near you.")
        if location:
            _run_nearby_search(location, label)

    if st.session_state.get("nearby_results"):
        col_note, col_clear = st.columns([5, 1])
        with col_clear:
            if st.button("✕ Clear", use_container_width=True, help="Show all destinations again"):
                for key in ("nearby_results", "nearby_context", "nearby_label"):
                    st.session_state.pop(key, None)
                clear_current_location()
                st.rerun()
        with col_note:
            context = st.session_state.get("nearby_context", {})
            st.success(
                f"Near {st.session_state.get('nearby_label', 'your location')}: "
                f"{context.get('message', 'Nearby destinations found.')} "
                + (f"Search radius: {float(context['radius_km']):g} km." if context.get("radius_km") else "")
            )

    categories = get_all_categories()

    # Convert database rows to dictionaries
    categories = [
        dict(category)
        for category in categories
    ]

    category_options = ["All Categories"]

    for category in categories:
        name = category.get("category_name")

        if name:
            category_options.append(name)

    # Category tiles link to ?category=<name>; turn that into the filter.
    linked_category = st.query_params.get("category")
    if linked_category:
        if linked_category in category_options:
            st.session_state["explore_category"] = linked_category
        del st.query_params["category"]

    selected_category = st.selectbox(
        "Tourism Category",
        category_options,
        key="explore_category",
    )

    nearby_results = st.session_state.get("nearby_results")
    if nearby_results:
        places = nearby_results
    elif search_query:
        places = [dict(place) for place in search_places(search_query, limit=300)]
    else:
        places = load_places()

    if selected_category != "All Categories":
        places = [
            place
            for place in places
            if str(
                place.get("category_name", "")
            ).lower()
            == selected_category.lower()
        ]

    if not places:
        st.markdown('<div class="section-title">Tourist Destinations</div>', unsafe_allow_html=True)
        st.info(
            "No destinations found. "
            "Try another search or category."
        )
        return

    # A specific search / nearby / category filter is a lookup, best served
    # by a plain result list. The default, unfiltered browse is where the
    # editorial horizontal-row treatment belongs.
    is_default_browse = (
        not search_query
        and not nearby_results
        and selected_category == "All Categories"
    )

    if not search_query and not nearby_results:
        current = None if selected_category == "All Categories" else selected_category
        render_category_showcase(load_places(), selected=current)

    if is_default_browse:
        st.markdown('<div class="section-title">Top places in each category</div>', unsafe_allow_html=True)
        _render_browse_rows(places)
    else:
        st.markdown('<div class="section-title">Tourist Destinations</div>', unsafe_allow_html=True)
        shown = places[:GRID_LIMIT]
        if len(places) > len(shown):
            st.caption(f"Showing the top {len(shown)} of {len(places)} destinations. Refine your search to see others.")
        else:
            st.caption(f"Showing {len(places)} destinations")
        render_place_grid(
            shown,
            columns=3,
            show_distance=bool(nearby_results),
        )

    st.markdown(
        """
        <div class="section-title">
            Destination Map
        </div>
        """,
        unsafe_allow_html=True,
    )

    render_map_view(places)


if __name__ == "__main__":
    render_explore_page()
