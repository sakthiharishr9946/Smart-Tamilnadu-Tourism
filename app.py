from pathlib import Path

import streamlit as st

from ui.theme import load_theme
from ui.components.navbar import render_navbar
from ui.components.scroll_effects import inject_scroll_reveal

from app_pages.explore import render_explore_page
from app_pages.recommendations import render_recommendations_page
from app_pages.itinerary import render_itinerary_page
from app_pages.chatbot import render_chatbot_page
from app_pages.place_details import render_place_details

from database.connection import initialize_database
from database.migrations import apply_migrations


def load_css():
    """
    Load all application CSS files.
    """

    styles_dir = (
        Path(__file__).parent
        / "ui"
        / "styles"
    )

    css_files = [
        "main.css",
        "cards.css",
        "navbar.css",
        "chatbot.css",
        "responsive.css",
    ]

    for css_file in css_files:

        css_path = (
            styles_dir
            / css_file
        )

        if not css_path.exists():
            continue

        try:

            css = css_path.read_text(
                encoding="utf-8"
            )

            st.markdown(
                f"""
                <style>
                {css}
                </style>
                """,
                unsafe_allow_html=True,
            )

        except Exception:
            continue


initialize_database()
apply_migrations()


def render_page(page):
    """
    Render the selected application page.
    """

    if page == "Explore":
        render_explore_page()

    elif page == "Recommendations":
        render_recommendations_page()

    elif page == "Itinerary":
        render_itinerary_page()

    elif page == "Chatbot":
        render_chatbot_page()

    else:
        render_explore_page()


def main():
    """
    Main Streamlit application entry point.
    """

    st.set_page_config(
        page_title="Smart Tamilnadu Tourism",
        page_icon="🌴",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    apply_migrations()

    # Global theme variables
    load_theme()

    # Application CSS
    load_css()

    # Scroll-triggered reveal animations
    inject_scroll_reveal()

    # --------------------------------------------------------
    # PLACE DETAILS
    # --------------------------------------------------------

    query_place_id = st.query_params.get(
        "place_id"
    )

    if query_place_id:

        try:
            st.session_state[
                "selected_place_id"
            ] = int(query_place_id)

        except (
            TypeError,
            ValueError,
        ):
            pass

        del st.query_params[
            "place_id"
        ]

    # --------------------------------------------------------
    # NAVIGATION
    # --------------------------------------------------------

    page = render_navbar()

    # --------------------------------------------------------
    # PLACE DETAILS
    # --------------------------------------------------------

    selected_place_id = (
        st.session_state.get(
            "selected_place_id"
        )
    )

    if selected_place_id:

        if st.button(
            "← Back to explore"
        ):
            st.session_state.pop(
                "selected_place_id",
                None,
            )

            st.rerun()

        render_place_details(
            selected_place_id
        )

    else:
        render_page(page)


if __name__ == "__main__":
    main()