from html import escape

import streamlit as st


def render_page_hero(eyebrow, title, subtitle, photo_categories=None, show_photos=True):
    """Page header in the same split layout as the Explore hero: editorial
    text on the left, photo cards of real places for this page on the right."""
    text_html = (
        f'<div class="hero-eyebrow reveal">{escape(eyebrow)}</div>'
        f'<div class="page-hero-title reveal">{escape(title)}</div>'
        '<div class="hero-editorial-rule reveal"></div>'
        f'<div class="hero-editorial-subtitle reveal">{escape(subtitle)}</div>'
    )
    if not show_photos:
        st.markdown(text_html, unsafe_allow_html=True)
        return

    from ui.components.hero_visual import pick_photo_places, render_photo_cards

    places = pick_photo_places(photo_categories, limit=3)
    if not places:
        st.markdown(text_html, unsafe_allow_html=True)
        return

    col_text, col_visual = st.columns([5, 7], gap="medium")
    with col_text:
        st.markdown(text_html, unsafe_allow_html=True)
    with col_visual:
        render_photo_cards(places)
