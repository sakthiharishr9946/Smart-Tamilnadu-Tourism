"""Browser GPS for Streamlit.

The page calls ``start_gps_request()`` when the traveller presses the GPS
button and ``poll_gps()`` on every run. While a request is pending, a
zero-height component (gps_frontend/index.html) asks the browser for its
position and hands the coordinates straight back to Python - no page
reload, so the session (filters, results) survives.
"""

from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

from services.location.current_location import set_current_location

_gps_component = components.declare_component(
    "browser_gps",
    path=str(Path(__file__).parent / "gps_frontend"),
)

GPS_ERRORS = {
    "denied": "Location permission was blocked. Click the location icon in your browser's address bar, "
              "allow access for this site, then press GPS again - or type a town in the box.",
    "unavailable": "Your device could not determine its position. Turn on location services "
                   "(Windows: Settings > Privacy & security > Location) or type a town in the box.",
    "timeout": "Finding your position took too long. Press GPS again, or type a town in the box.",
    "no_answer": "No location yet - answer your browser's location prompt (look for it near the address bar), "
                 "then press GPS again, or type a town in the box.",
    "insecure": "Browsers only share location on secure pages. Open the app at http://localhost:8501 "
                "(or over https) instead of a network IP address.",
    "unsupported": "This browser does not support location access. Type a town below instead.",
}


def start_gps_request():
    st.session_state["gps_request_id"] = st.session_state.get("gps_request_id", 0) + 1
    st.session_state["gps_pending"] = True


def gps_pending():
    return bool(st.session_state.get("gps_pending"))


def poll_gps():
    """Advance a pending GPS request.

    Returns ``(location, accuracy_m, error)``. All three are None while the
    browser is still waiting for permission or a fix.
    """
    if not gps_pending():
        return None, None, None

    value = _gps_component(key=f"gps_{st.session_state['gps_request_id']}", default=None)
    if not value:
        return None, None, None

    st.session_state["gps_pending"] = False
    if value.get("error"):
        return None, None, GPS_ERRORS.get(value["error"], GPS_ERRORS["unavailable"])
    try:
        latitude, longitude = float(value["latitude"]), float(value["longitude"])
    except (KeyError, TypeError, ValueError):
        return None, None, GPS_ERRORS["unavailable"]
    set_current_location(latitude, longitude)
    return (latitude, longitude), value.get("accuracy"), None
