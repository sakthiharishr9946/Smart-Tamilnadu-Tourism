import streamlit as st


def render_location_button():
    st.markdown(
        """
        <div class="info-card">
            <strong>📍 Find places near you</strong>
            <p>
                Use your current location to discover
                nearby Tamil Nadu tourist destinations.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if st.button(
        "📍 Use My Current Location",
        key="current_location_button",
        use_container_width=True,
    ):
        st.session_state["request_location"] = True

    return st.session_state.get(
        "request_location",
        False,
    )


def set_location(latitude, longitude):
    try:
        st.session_state["user_location"] = {
            "latitude": float(latitude),
            "longitude": float(longitude),
        }

        st.session_state["request_location"] = False

        return True

    except (TypeError, ValueError):
        return False


def clear_location():
    st.session_state.pop(
        "user_location",
        None,
    )

    st.session_state["request_location"] = False


def get_location():
    return st.session_state.get(
        "user_location"
    )