import streamlit as st


def render_budget_card(budget):
    if not budget:
        st.info("No budget information available.")
        return

    transport = budget.get("transport", 0)
    food = budget.get("food", 0)
    accommodation = budget.get(
        "accommodation",
        0,
    )
    entry_fees = budget.get(
        "entry_fees",
        0,
    )
    miscellaneous = budget.get(
        "miscellaneous",
        0,
    )
    total = budget.get(
        "total",
        0,
    )

    lines = (
        ("Accommodation", accommodation),
        ("Food", food),
        ("Transportation", transport),
        ("Miscellaneous", miscellaneous),
        ("Entry fees", entry_fees),
    )
    total_value = float(total) or 1.0
    rows = []
    for label, value in lines:
        share = max(0.0, float(value)) / total_value * 100
        rows.append(
            '<div class="budget-item">'
            '<div class="budget-item-head">'
            f'<span class="budget-label">{label}</span>'
            f'<span class="budget-value">₹{float(value):,.0f}'
            f'<span class="budget-share">{share:.0f}%</span></span>'
            '</div>'
            # The bar shows each line's share of the total at a glance.
            f'<div class="budget-bar"><span style="--share:{share:.1f}%"></span></div>'
            '</div>'
        )

    html = (
        '<div class="budget-card reveal">'
        '<div class="budget-total-label">Estimated total</div>'
        f'<div class="budget-total">₹{float(total):,.0f}</div>'
        + "".join(rows)
        + '</div>'
    )

    st.markdown(html, unsafe_allow_html=True)


def render_budget_summary(budget):
    if not budget:
        return

    total = budget.get("total", 0)

    try:
        total = float(total)
    except (TypeError, ValueError):
        total = 0.0

    st.metric(
        "Estimated Trip Cost",
        f"₹{total:,.0f}",
    )