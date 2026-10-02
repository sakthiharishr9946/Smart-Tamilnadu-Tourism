from services.budget.calculator import (
    calculate_accommodation_cost,
    calculate_entry_fees,
    calculate_food_cost,
    calculate_total_budget,
    calculate_transport_cost,
)


def test_transport_cost_uses_distance_and_rate():
    assert calculate_transport_cost(100, 8) == 800.0
    assert calculate_transport_cost(-5, 8) == 0.0
    assert calculate_transport_cost("far", 8) == 0.0


def test_food_and_accommodation_scale_with_travelers_and_time():
    assert calculate_food_cost(2, 3, 500) == 3000.0
    assert calculate_accommodation_cost(2, 2, 1200) == 4800.0
    # A day trip has no nights to pay for.
    assert calculate_accommodation_cost(2, 0, 1200) == 0.0


def test_entry_fees_ignore_missing_and_bad_values():
    places = [{"entry_fee": 50}, {"entry_fee": None}, {"entry_fee": "free"}, {}]
    assert calculate_entry_fees(places, travelers=3) == 150.0


def test_total_budget_is_sum_of_parts():
    budget = calculate_total_budget(
        distance_km=39.1, travelers=2, days=3, nights=2, places=[{"entry_fee": 40}],
        transport_cost_per_km=8, food_cost_per_person_per_day=500,
        accommodation_cost_per_person_per_night=1200, miscellaneous_cost_per_day=200,
    )
    parts = ("transport", "food", "accommodation", "entry_fees", "miscellaneous")
    assert budget["total"] == round(sum(budget[part] for part in parts), 2)
    assert budget["transport"] == 312.8
    assert budget["entry_fees"] == 80.0
