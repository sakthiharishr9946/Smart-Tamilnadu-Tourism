import streamlit as st


def render_search_bar(
    placeholder="Search tourist places, cities, temples, beaches...",
):
    search_query = st.text_input(
        "Search",
        value=st.session_state.get(
            "search_query",
            "",
        ),
        placeholder=placeholder,
        label_visibility="collapsed",
        key="tourism_search_input",
    )

    st.session_state["search_query"] = (
        search_query.strip()
    )

    return st.session_state["search_query"]