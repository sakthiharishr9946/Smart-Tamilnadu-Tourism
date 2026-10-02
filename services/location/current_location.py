from typing import Optional, Tuple

import streamlit as st


def get_current_location() -> Optional[Tuple[float, float]]:
    if "user_location" not in st.session_state:
        return None

    location = st.session_state.get("user_location")

    if not location:
        return None

    latitude = location.get("latitude")
    longitude = location.get("longitude")

    if latitude is None or longitude is None:
        return None

    try:
        return float(latitude), float(longitude)
    except (TypeError, ValueError):
        return None


def set_current_location(latitude: float, longitude: float) -> None:
    st.session_state["user_location"] = {
        "latitude": float(latitude),
        "longitude": float(longitude),
    }


def clear_current_location() -> None:
    st.session_state.pop("user_location", None)


def has_current_location() -> bool:
    return get_current_location() is not None
