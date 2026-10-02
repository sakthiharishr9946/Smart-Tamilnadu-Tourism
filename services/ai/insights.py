from services.ai.groq_client import generate_ai_text, is_ai_enabled

_ITINERARY_SYSTEM_PROMPT = """
You are a Tamil Nadu travel expert writing a short, practical note for a
traveler about the day-by-day itinerary they were just given. You are
given the REAL schedule the app generated - do not invent extra stops,
days, or times that are not listed. Mention useful, realistic travel
tips (pacing, what to carry, best time to start) in 3-4 sentences. Do
not repeat the schedule back verbatim; add value beyond it.
"""

_BUDGET_SYSTEM_PROMPT = """
You are a Tamil Nadu travel budgeting expert writing a short note about
a cost estimate the app just calculated. You are given the REAL cost
breakdown - do not invent extra costs or change the numbers. Point out
where the money is going and 2-3 realistic ways to save, in 3-4
sentences. Keep numbers in Indian Rupees (Rs) as given.
"""


def _format_itinerary(itinerary):
    lines = []
    for day in itinerary:
        day_number = day.get("day", 1)
        for stop in day.get("schedule", []):
            place = stop.get("place", {})
            lines.append(
                f"Day {day_number}: {stop.get('start_time')}-{stop.get('end_time')} "
                f"{place.get('place_name', 'Unknown place')} "
                f"({place.get('category_name', 'destination')}, {place.get('district', 'Tamil Nadu')})"
            )
    return "\n".join(lines)


def generate_itinerary_notes(itinerary):
    if not is_ai_enabled() or not itinerary:
        return None

    schedule_text = _format_itinerary(itinerary)
    if not schedule_text:
        return None

    return generate_ai_text(
        _ITINERARY_SYSTEM_PROMPT,
        f"Generated itinerary:\n{schedule_text}",
    )


def _format_budget(budget, travelers, days, nights, distance_km, budget_level):
    return (
        f"Travelers: {travelers}, Days: {days}, Nights: {nights}, "
        f"Distance: {distance_km} km, Budget level: {budget_level}\n"
        f"Transport: Rs {budget.get('transport', 0)}\n"
        f"Food: Rs {budget.get('food', 0)}\n"
        f"Accommodation: Rs {budget.get('accommodation', 0)}\n"
        f"Entry fees: Rs {budget.get('entry_fees', 0)}\n"
        f"Miscellaneous: Rs {budget.get('miscellaneous', 0)}\n"
        f"Total: Rs {budget.get('total', 0)}"
    )


def generate_budget_notes(budget, travelers, days, nights, distance_km, budget_level):
    if not is_ai_enabled() or not budget:
        return None

    return generate_ai_text(
        _BUDGET_SYSTEM_PROMPT,
        f"Cost breakdown:\n{_format_budget(budget, travelers, days, nights, distance_km, budget_level)}",
    )
