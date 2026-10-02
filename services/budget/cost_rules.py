COST_RULES = {
    "transport": {
        "budget": 6.0,
        "standard": 8.0,
        "premium": 12.0,
    },
    "food_per_person_per_day": {
        "budget": 300.0,
        "standard": 500.0,
        "premium": 900.0,
    },
    "accommodation_per_person_per_night": {
        "budget": 700.0,
        "standard": 1200.0,
        "premium": 2500.0,
    },
    "miscellaneous_per_day": {
        "budget": 100.0,
        "standard": 200.0,
        "premium": 400.0,
    },
}


BUDGET_LEVELS = [
    "budget",
    "standard",
    "premium",
]


def get_cost_rule(category, budget_level="standard"):
    if category not in COST_RULES:
        return 0.0

    if budget_level not in BUDGET_LEVELS:
        budget_level = "standard"

    return COST_RULES[category].get(
        budget_level,
        0.0,
    )


def get_budget_rules(budget_level="standard"):
    if budget_level not in BUDGET_LEVELS:
        budget_level = "standard"

    return {
        category: values.get(
            budget_level,
            0.0,
        )
        for category, values in COST_RULES.items()
    }


def calculate_estimated_daily_cost(
    budget_level="standard",
):
    rules = get_budget_rules(budget_level)

    return round(
        rules["food_per_person_per_day"]
        + rules["accommodation_per_person_per_night"]
        + rules["miscellaneous_per_day"],
        2,
    )