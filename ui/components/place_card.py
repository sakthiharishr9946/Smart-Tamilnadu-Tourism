import streamlit as st
from html import escape

from ui.category_content import resolve_description
from ui.components.crowd_badge import get_crowd_badge_class, get_crowd_icon
from services.crowd.estimator import estimate_crowd_level


def render_place_card(place, show_distance=True):
    place_name_raw = str(place.get(
        "place_name",
        "Unknown Place",
    ))
    place_name = escape(place_name_raw)

    description = escape(
        resolve_description(
            place.get("description"),
            place_name_raw,
            place.get("category_name"),
        )
    )

    district = escape(str(place.get(
        "district",
        "Tamil Nadu",
    )))

    category = escape(str(place.get(
        "category_name",
        "Tourist Attraction",
    )))

    rating = place.get("rating") or 0

    try:
        rating = float(rating)
    except (TypeError, ValueError):
        rating = 0.0

    rating_count = place.get("rating_count") or 0

    distance = place.get(
        "distance_km"
    )

    image_url = place.get(
        "image_url"
    )
    current_status = place.get("current_status") or {}
    status_text = escape(str(current_status.get("status", "")))
    status_html = f'<div class="place-card-status">Status: {status_text}</div>' if status_text else ""

    crowd_level, _crowd_score = estimate_crowd_level(place.get("category_name"))
    crowd_class = get_crowd_badge_class(crowd_level)
    crowd_icon = get_crowd_icon(crowd_level)
    crowd_html = f'<span class="{crowd_class}">{crowd_icon} {escape(str(crowd_level))}</span>'

    if rating > 0:
        rating_html = f'<span class="place-card-rating">⭐ {rating:.1f} <span class="place-card-rating-count">({int(rating_count)})</span></span>'
    else:
        rating_html = '<span class="place-card-rating place-card-rating-empty">Not yet rated</span>'

    distance_html = (
        f'<span class="place-card-distance">📍 {distance:.1f} km</span>'
        if show_distance and distance is not None
        else ""
    )

    image_html = (
        f'<img src="{escape(str(image_url), quote=True)}" class="place-card-image">'
        if image_url
        else ""
    )

    card_html = (
        '<div class="place-card reveal">'
        f'{image_html}'
        f'<div class="place-card-title">{place_name}</div>'
        f'<div class="place-card-location">📍 {district} • {category}</div>'
        f'<div class="place-card-description">{description}</div>'
        f'{status_html}'
        '<div class="place-card-footer">'
        f'{rating_html}'
        f'{crowd_html}'
        f'{distance_html}'
        '</div>'
        '</div>'
    )

    st.markdown(card_html, unsafe_allow_html=True)


def render_place_card_with_button(
    place,
    button_label="View Details",
    show_distance=True,
):
    render_place_card(
        place,
        show_distance=show_distance,
    )

    place_id = place.get(
        "place_id"
    )

    if st.button(
        button_label,
        key=f"place_{place_id}",
        use_container_width=True,
    ):
        st.session_state[
            "selected_place_id"
        ] = place_id

        return True

    return False
