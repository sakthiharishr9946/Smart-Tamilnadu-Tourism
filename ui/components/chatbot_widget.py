from html import escape
from urllib.parse import quote

import streamlit as st

from services.ai.groq_client import is_ai_enabled
from services.chatbot.chatbot import generate_ai_response

QUICK_PROMPTS = [
    "Beaches near Chennai",
    "Plan a 3-day trip",
    "Temples worth visiting",
    "Hill stations to escape the heat",
    "Upcoming festivals",
]


def initialize_chat():
    if "chat_messages" not in st.session_state:
        st.session_state["chat_messages"] = []


def _render_transcript():
    messages = st.session_state["chat_messages"]

    if not messages:
        st.markdown(
            '<div class="chat-empty">Ask about destinations, itineraries, budgets or festivals '
            "&mdash; or try one of the prompts below.</div>",
            unsafe_allow_html=True,
        )
        return

    rows = []
    for message in messages:
        role = message.get("role", "assistant")
        content = escape(str(message.get("content", "")))
        avatar = "🧑" if role == "user" else "🤖"

        rows.append(
            f'<div class="chat-row {role}">'
            f'<div class="chat-avatar">{avatar}</div>'
            f'<div class="chat-bubble {role}">{content}</div>'
            "</div>"
        )

    st.markdown('<div class="chat-window">' + "".join(rows) + "</div>", unsafe_allow_html=True)


def _render_quick_prompts():
    chips = "".join(
        f'<a class="chat-chip" href="?chat_prompt={quote(prompt)}" target="_self">{escape(prompt)}</a>'
        for prompt in QUICK_PROMPTS
    )

    st.markdown(f'<div class="chat-chip-row">{chips}</div>', unsafe_allow_html=True)


def _handle_message(user_message):
    st.session_state["chat_messages"].append({"role": "user", "content": user_message})

    with st.spinner("Thinking..."):
        response = generate_ai_response(user_message)

    st.session_state["chat_messages"].append({"role": "assistant", "content": response})


def render_chatbot():
    initialize_chat()

    ai_status = (
        "Powered by Groq AI, grounded in live destination data."
        if is_ai_enabled()
        else "Rule-based answers &mdash; add a GROQ_API_KEY to enable conversational AI."
    )
    st.markdown(f'<div class="ghost-toolbar-label reveal">{ai_status}</div>', unsafe_allow_html=True)

    queued_prompt = st.query_params.get("chat_prompt")
    if queued_prompt:
        st.query_params.clear()
        _handle_message(queued_prompt)

    _render_transcript()
    _render_quick_prompts()

    user_message = st.chat_input("Ask about Tamil Nadu tourism...")

    if user_message:
        _handle_message(user_message)
        st.rerun()


def clear_chat():
    st.session_state["chat_messages"] = []
