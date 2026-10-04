from services.ai.groq_client import generate_ai_text, is_ai_enabled

_ITINERARY_SYSTEM_PROMPT = """
You are a friendly local Tamil Nadu travel guide adding a short personal
note to the trip plan a traveller was just given. Write like a person,
not a report: warm, plain English, second person ("you"), 3-4 sentences
in one paragraph. No headings, no "Day 1:" labels, no bullet points.

Use ONLY what the plan says: the stops, their times, the drive times and
the lunch break. Never invent anything that is not listed - no walks,
distances, drive times, stalls, shops, prices, opening hours, dress
codes or events. Do not repeat the schedule back. Add value with
general, safe advice: pacing, an early start, water and sun protection,
modest clothing and leaving footwear outside at temples, keeping some
cash for small entry fees or parking.
"""

_BUDGET_SYSTEM_PROMPT = """
You are a friendly Tamil Nadu travel guide explaining a trip cost
estimate the app just worked out. Write like a person: warm, plain
English, second person ("you"), one paragraph of 3 sentences, no
headings or bullet points. Use ONLY the numbers given - never add costs
or change figures - and keep amounts in Indian Rupees (Rs). Say where
most of the money goes and suggest 2 realistic ways to save.
"""


def _format_itinerary(itinerary):
    lines = []
    for day in itinerary:
        day_number = day.get("day", 1)
        # "entries" (newer plans) also carry drives and lunch breaks.
        for stop in day.get("entries") or day.get("schedule", []):
            if stop.get("kind") == "lunch":
                lines.append(f"Day {day_number}: {stop.get('start_time')}-{stop.get('end_time')} lunch break")
                continue
            if stop.get("lunch_before"):
                lunch = stop["lunch_before"]
                lines.append(f"Day {day_number}: {lunch['start_time']}-{lunch['end_time']} lunch break")
            place = stop.get("place", {})
            drive = stop.get("travel_minutes")
            drive_text = f", after a {drive} min drive" if drive else ""
            lines.append(
                f"Day {day_number}: {stop.get('start_time')}-{stop.get('end_time')} "
                f"{place.get('place_name', 'Unknown place')} "
                f"({place.get('category_name', 'destination')}, {place.get('district', 'Tamil Nadu')}{drive_text})"
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
