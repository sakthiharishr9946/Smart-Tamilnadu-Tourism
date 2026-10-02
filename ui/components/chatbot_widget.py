import re
from html import escape

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


_BULLET_RE = re.compile(r"^\s*(?:[-*•]|(?P<number>\d+)[.)])\s+")
_BOLD_RE = re.compile(r"\*\*(.+?)\*\*")


def format_message(text):
    """Chat text (with simple Markdown: **bold**, "- " / "1. " lists) as safe HTML.

    The transcript is one hand-built HTML block, where Streamlit does not
    apply Markdown, so answers used to show raw "**" and "- " marks.
    """
    blocks, items = [], []
    list_tag = "ul"

    def flush_list():
        if items:
            blocks.append(f"<{list_tag}>" + "".join(f"<li>{item}</li>" for item in items) + f"</{list_tag}>")
            items.clear()

    def inline(value):
        return _BOLD_RE.sub(r"<strong>\1</strong>", escape(value.strip()))

    for line in str(text or "").splitlines():
        if not line.strip():
            flush_list()
            continue
        bullet = _BULLET_RE.match(line)
        if bullet:
            tag = "ol" if bullet.group("number") else "ul"
            if items and tag != list_tag:
                flush_list()
            list_tag = tag
            items.append(inline(line[bullet.end():]))
        else:
            flush_list()
            blocks.append(f"<p>{inline(line)}</p>")
    flush_list()
    return "".join(blocks)


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
        content = format_message(message.get("content", ""))
        avatar = "🧑" if role == "user" else "🤖"

        rows.append(
            f'<div class="chat-row {role}">'
            f'<div class="chat-avatar">{avatar}</div>'
            f'<div class="chat-bubble {role}">{content}</div>'
            "</div>"
        )

    st.markdown('<div class="chat-window">' + "".join(rows) + "</div>", unsafe_allow_html=True)


def _render_quick_prompts():
    """Suggested questions as real buttons.

    They used to be <a href="?chat_prompt=..."> links, which reload the
    page: Streamlit then starts a new session, forgets the open page and
    the conversation, and the app fell back to Explore.
    """
    chips = st.container(key="chat_chips")
    columns = chips.columns(len(QUICK_PROMPTS), gap="small")
    for index, prompt in enumerate(QUICK_PROMPTS):
        with columns[index]:
            if st.button(prompt, key=f"chat_chip_{index}", use_container_width=True):
                return prompt
    return None


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

    # Old bookmarked links may still carry ?chat_prompt=...
    queued_prompt = st.query_params.get("chat_prompt")
    if queued_prompt:
        del st.query_params["chat_prompt"]
        _handle_message(queued_prompt)

    _render_transcript()
    chip_prompt = _render_quick_prompts()

    user_message = st.chat_input("Ask about Tamil Nadu tourism...") or chip_prompt

    if user_message:
        _handle_message(user_message)
        st.rerun()


def clear_chat():
    st.session_state["chat_messages"] = []
