import streamlit as st

from ui.components.place_card import (
    render_place_card_with_button,
)


def render_place_grid(
    places,
    columns=3,
    show_distance=True,
):
    if not places:
        st.info(
            "No tourist places found."
        )
        return

    try:
        columns = max(1, int(columns))
    except (TypeError, ValueError):
        columns = 3

    for start in range(
        0,
        len(places),
        columns,
    ):
        row_places = places[
            start:start + columns
        ]

        cols = st.columns(
            len(row_places)
        )

        for index, place in enumerate(
            row_places
        ):
            with cols[index]:
                render_place_card_with_button(
                    place,
                    show_distance=show_distance,
                )