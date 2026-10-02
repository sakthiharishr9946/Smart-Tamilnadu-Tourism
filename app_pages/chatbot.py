import streamlit as st

from ui.components.chatbot_widget import render_chatbot
from ui.components.page_hero import render_page_hero


def render_chatbot_page():
    render_page_hero(
        "Travel assistant",
        "Ask about Tamil Nadu",
        "Ask for places in a district, the best waterfalls or beaches, festivals and trip ideas.",
        photo_categories=["Cultural", "Waterfall", "Beach"],
    )
    render_chatbot()


if __name__ == "__main__":
    render_chatbot_page()
