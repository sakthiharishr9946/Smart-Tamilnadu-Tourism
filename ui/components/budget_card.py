import streamlit as st


DEFAULT_CURRENCY_RATES = {
    "₹ INR": {
        "symbol": "₹",
        "rate": 1.0,
        "code": "INR",
    },
    "$ USD": {
        "symbol": "$",
        "rate": 1 / 83.0,
        "code": "USD",
    },
    "€ EUR": {
        "symbol": "€",
        "rate": 1 / 90.0,
        "code": "EUR",
    },
    "£ GBP": {
        "symbol": "£",
        "rate": 1 / 105.0,
        "code": "GBP",
    },
    "¥ JPY": {
        "symbol": "¥",
        "rate": 1 / 0.56,
        "code": "JPY",
    },
    "د.إ AED": {
        "symbol": "د.إ ",
        "rate": 1 / 22.6,
        "code": "AED",
    },
}


def _convert(value, currency, currency_rates):
    try:
        value = float(value or 0)
    except (TypeError, ValueError):
        value = 0.0

    currency_data = currency_rates.get(
        currency,
        DEFAULT_CURRENCY_RATES["₹ INR"],
    )

    return value * float(
        currency_data.get("rate", 1.0)
    )


def _format_amount(
    value,
    currency,
    currency_rates,
):
    currency_data = currency_rates.get(
        currency,
        DEFAULT_CURRENCY_RATES["₹ INR"],
    )

    symbol = currency_data.get(
        "symbol",
        "₹",
    )

    converted = _convert(
        value,
        currency,
        currency_rates,
    )

    return f"{symbol}{converted:,.0f}"


def render_budget_card(
    budget,
    currency="₹ INR",
    currency_rates=None,
):
    if not budget:
        st.info(
            "No budget information available."
        )
        return

    currency_rates = (
        currency_rates
        or DEFAULT_CURRENCY_RATES
    )

    transport = budget.get(
        "transport",
        0,
    )

    food = budget.get(
        "food",
        0,
    )

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
        (
            "Accommodation",
            accommodation,
        ),
        (
            "Food",
            food,
        ),
        (
            "Transportation",
            transport,
        ),
        (
            "Miscellaneous",
            miscellaneous,
        ),
        (
            "Entry fees",
            entry_fees,
        ),
    )

    try:
        total_value = float(total)
    except (TypeError, ValueError):
        total_value = 0.0

    denominator = (
        total_value
        if total_value > 0
        else 1.0
    )

    rows = []

    for label, value in lines:

        try:
            numeric_value = float(
                value or 0
            )
        except (TypeError, ValueError):
            numeric_value = 0.0

        share = (
            max(
                0.0,
                numeric_value,
            )
            / denominator
            * 100
        )

        rows.append(
            '<div class="budget-item">'
            '<div class="budget-item-head">'
            f'<span class="budget-label">{label}</span>'
            f'<span class="budget-value">'
            f'{_format_amount(value, currency, currency_rates)}'
            f'<span class="budget-share">'
            f'{share:.0f}%'
            "</span>"
            "</span>"
            "</div>"
            f'<div class="budget-bar">'
            f'<span style="--share:{share:.1f}%"></span>'
            "</div>"
            "</div>"
        )

    html = (
        '<div class="budget-card reveal">'
        '<div class="budget-total-label">'
        "Estimated total"
        "</div>"
        f'<div class="budget-total">'
        f'{_format_amount(total, currency, currency_rates)}'
        "</div>"
        + "".join(rows)
        + "</div>"
    )

    st.markdown(
        html,
        unsafe_allow_html=True,
    )


def render_budget_summary(
    budget,
    currency="₹ INR",
    currency_rates=None,
):
    if not budget:
        return

    currency_rates = (
        currency_rates
        or DEFAULT_CURRENCY_RATES
    )

    total = budget.get(
        "total",
        0,
    )

    try:
        total = float(total)
    except (TypeError, ValueError):
        total = 0.0

    st.metric(
        "Estimated Trip Cost",
        _format_amount(
            total,
            currency,
            currency_rates,
        ),
    )