import streamlit as st


def get_crowd_badge_class(crowd_level):
    if not crowd_level:
        return "crowd-badge"

    level = str(crowd_level).strip().lower()

    if level == "low":
        return "crowd-badge crowd-low"

    if level == "medium":
        return "crowd-badge crowd-medium"

    if level == "high":
        return "crowd-badge crowd-high"

    return "crowd-badge"


def get_crowd_icon(crowd_level):
    level = str(crowd_level).strip().lower()

    if level == "low":
        return "🟢"

    if level == "medium":
        return "🟡"

    if level == "high":
        return "🔴"

    return "⚪"


def render_crowd_badge(crowd_level):
    level = (
        str(crowd_level).strip().title()
        if crowd_level
        else "Unknown"
    )

    badge_class = get_crowd_badge_class(
        crowd_level
    )

    icon = get_crowd_icon(
        crowd_level
    )

    st.markdown(
        f'<span class="{badge_class}">{icon} Crowd: {level}</span>',
        unsafe_allow_html=True,
    )


def render_crowd_info(
    crowd_level,
    crowd_probability=None,
):
    level = (
        str(crowd_level).strip().title()
        if crowd_level
        else "Unknown"
    )

    icon = get_crowd_icon(
        crowd_level
    )

    probability_text = ""

    if crowd_probability is not None:
        try:
            probability = float(
                crowd_probability
            )

            if probability <= 1:
                probability *= 100

            probability_text = (
                f" • Confidence: "
                f"{probability:.1f}%"
            )
        except (TypeError, ValueError):
            probability_text = ""

    info_html = (
        '<div class="info-card">'
        f'<strong>{icon} Estimated crowd: {level}</strong>'
        f'<p>{get_crowd_description(level)}{probability_text}</p>'
        # No public source publishes live visitor counts, so say what the
        # estimate is based on rather than presenting it as a measurement.
        '<p class="info-card-note">Estimated from the type of place and local festivals, '
        'not live visitor counts.</p>'
        '</div>'
    )

    st.markdown(info_html, unsafe_allow_html=True)


def get_crowd_description(level):
    descriptions = {
        "Low": (
            "This destination is expected to have "
            "relatively low visitor activity."
        ),
        "Medium": (
            "Moderate visitor activity is expected. "
            "Plan your visit accordingly."
        ),
        "High": (
            "High visitor activity is expected. "
            "Consider visiting during a less busy time."
        ),
        "Unknown": (
            "Crowd information is currently unavailable."
        ),
    }

    return descriptions.get(
        level,
        descriptions["Unknown"],
    )