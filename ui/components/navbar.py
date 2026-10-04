import streamlit as st


def render_navbar(active_page="Explore"):
    pages = [
        "Explore",
        "Recommendations",
        "Itinerary",
        "Chatbot",
    ]

    st.markdown(
        """
        <div class="navbar">
            <div class="navbar-brand">
                <div>
                    <p class="navbar-title">
                        Smart Tamilnadu Tourism
                    </p>
                    <p class="navbar-subtitle">
                        Discover • Plan • Explore
                    </p>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    url_page = st.query_params.get(
        "page"
    )

    if (
        "active_page" not in st.session_state
        and url_page in pages
    ):
        st.session_state[
            "active_page"
        ] = url_page

    selected_page = st.session_state.get(
        "active_page",
        active_page,
    )

    if (
        st.query_params.get("page")
        != selected_page
    ):
        st.query_params[
            "page"
        ] = selected_page

    nav = st.container(
        key="main_nav"
    )

    cols = nav.columns(
        len(pages),
        gap="small",
    )

    for index, page in enumerate(pages):

        with cols[index]:

            button_type = (
                "primary"
                if page == selected_page
                else "secondary"
            )

            if st.button(
                page,
                key=f"nav_{page.lower()}",
                use_container_width=True,
                type=button_type,
            ):
                st.session_state[
                    "active_page"
                ] = page

                st.query_params[
                    "page"
                ] = page

                st.session_state.pop(
                    "selected_place_id",
                    None,
                )

                st.rerun()

    return selected_page