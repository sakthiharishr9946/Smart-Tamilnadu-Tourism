from services.ai.groq_client import generate_ai_text, is_ai_enabled
from services.chatbot.knowledge import search_knowledge
from services.chatbot.prompts import CONVERSATIONAL_SYSTEM_PROMPT, build_conversational_prompt
from services.chatbot.tools import (
    get_place_information,
    search_tourist_places,
)
from database.queries import find_places, get_festivals_for_place, search_places
from services.chatbot.understanding import find_category, find_district, wants_near_me
from services.location.current_location import get_current_location
from services.search.start_search import start_search
from services.status.place_status import get_current_status


def detect_intent(message):
    if not message:
        return "general"

    text = message.lower().strip()

    if any(
        word in text
        for word in [
            "near",
            "nearby",
            "around",
            "closest",
        ]
    ):
        return "nearby"

    if any(
        word in text
        for word in [
            "place",
            "places",
            "visit",
            "tourist",
            "destination",
        ]
    ):
        return "places"

    if any(
        word in text
        for word in [
            "temple",
            "beach",
            "hill",
            "waterfall",
            "wildlife",
        ]
    ):
        return "category"

    if any(
        word in text
        for word in [
            "festival",
            "festivals",
            "celebration",
        ]
    ):
        return "festival"

    if any(
        word in text
        for word in [
            "budget",
            "cost",
            "expense",
            "price",
        ]
    ):
        return "budget"

    if any(
        word in text
        for word in [
            "itinerary",
            "trip plan",
            "travel plan",
            "schedule",
        ]
    ):
        return "itinerary"

    return "general"


def extract_search_term(message):
    if not message:
        return ""

    prefixes = [
        "tell me about",
        "information about",
        "details about",
        "show me",
        "find",
        "search for",
        "places to visit",
        "tourist places",
    ]

    text = message.strip()

    for prefix in prefixes:
        if text.lower().startswith(prefix):
            return text[len(prefix):].strip()

    return text


def _find_named_place(message):
    """A specific destination named in the message ("tell me about Marina Beach")."""
    term = extract_search_term(message).strip(" ?.!")
    if len(term) < 4:
        return None
    for row in search_places(term, limit=3):
        place = dict(row)
        if str(place.get("place_name", "")).casefold() in (message or "").casefold():
            return place
    return None


def _describe_places(places, heading):
    lines = []
    for index, row in enumerate(places[:8], 1):
        place = dict(row)
        description = str(place.get("description") or "").strip()
        if len(description) > 140:
            description = description[:137].rsplit(" ", 1)[0] + "..."
        detail = f" - {description}" if len(description) >= 40 else ""
        lines.append(f"{index}. {place.get('place_name')} ({place.get('district')}, {place.get('category_name')}){detail}")
    return heading + "\n\n" + "\n".join(lines)


def _once_each(festivals):
    """Each festival once, at its earliest listed date, in date order."""
    first = {}
    for festival in sorted(festivals, key=lambda f: str(f.get("start_date") or "9999")):
        first.setdefault(str(festival.get("festival_name") or "").strip().casefold(), festival)
    return list(first.values())


def _festival_answer(district):
    import datetime
    today = datetime.date.today().isoformat()
    rows = [dict(r) for r in get_festivals_for_place(-1, district)]
    local = _once_each([r for r in rows if district and r.get("district") == district])
    # Holidays are stored for this year and next: keep each festival's next date only.
    upcoming = _once_each([r for r in rows if r.get("district") is None
                           and str(r.get("start_date") or "") >= today])[:6]
    parts = []
    if local:
        parts.append(f"Festivals in {district}: " + "; ".join(
            r["festival_name"] + (f" (month {r['month']})" if r.get("month") else "") for r in local[:8]))
    if upcoming:
        parts.append("Upcoming across Tamil Nadu: " + "; ".join(
            f"{r['festival_name']} on {r['start_date']}" for r in upcoming))
    return "\n".join(parts) or None


def _grounded_answer(message):
    """Answer from the database when the message names a district, a
    category or a specific destination. Returns None otherwise."""
    district = find_district(message)
    category = find_category(message)
    text = (message or "").lower()

    if any(word in text for word in ("festival", "festivals", "celebration", "event")):
        answer = _festival_answer(district)
        if answer:
            return answer

    if wants_near_me(message) and not district:
        return None  # handled by the GPS-based nearby flow

    named = _find_named_place(message)
    if named and not (district and category):
        description = str(named.get("description") or "").strip()
        return (f"{named['place_name']} is a {str(named.get('category_name') or 'tourist').lower()} destination "
                f"in {named.get('district')} district. {description}").strip()

    if district or category:
        places = [dict(p) for p in find_places(district=district, category_name=category, limit=8)]
        if not places and district and category:
            places = [dict(p) for p in find_places(district=district, limit=8)]
            heading = f"I don't have {category.lower()} listings in {district}, but these are its top destinations:"
        else:
            what = f"{category.lower()} destinations" if category else "destinations"
            where = f" in {district}" if district else " in Tamil Nadu"
            heading = f"Top {what}{where}:"
        if places:
            return _describe_places(places, heading)
    return None


def _format_places(places, prefix="Here are some suitable places:"):
    names = [dict(place).get("place_name", "Unknown Place") for place in places[:5]]
    if not names:
        return "I couldn't find matching places in the current tourism data."
    return prefix + "\n\n" + "\n".join(f"{index}. {name}" for index, name in enumerate(names, 1))


def generate_response(message):
    if not message or not message.strip():
        return (
            "Hello! I can help you explore Tamil Nadu "
            "tourist destinations, temples, beaches, "
            "festivals, itineraries and budgets."
        )

    intent = detect_intent(message)
    search_term = extract_search_term(message)

    if not any(word in message.lower() for word in ["good to visit", "visit now", "open now", "status", "condition"]):
        grounded = _grounded_answer(message)
        if grounded:
            return grounded

    if any(word in message.lower() for word in ["good to visit", "visit now", "open now", "status", "condition"]):
        place = get_place_information(search_term)
        if not place:
            place = _find_named_place(message)
        if place:
            place = dict(place)
            current = get_current_status(place["place_id"])
            response = f"{place['place_name']}: {current['status']}."
            if current.get("details"):
                response += f" {current['details']}"
            if not current.get("checked_at"):
                response += " No recent source-verified condition is available, so check locally before travel."
            return response

    if intent == "places":
        places = search_tourist_places(search_term)

        if not places:
            return (
                "I couldn't find matching tourist places. "
                "Try searching for a city, district or "
                "tourism category."
            )

        return _format_places(places, "Here are some places you can explore:")

    if intent == "category":
        places = search_tourist_places(search_term)

        if places:
            return _format_places(places, "Some matching destinations are:")

    if intent == "nearby":
        location = get_current_location()
        if location:
            places, _ = start_search(location[0], location[1])
        else:
            places = []

        if places:
            return _format_places(places, "Nearby destinations ranked for you:")

        return (
            "I don't know where you are yet. Press the 📍 GPS button on the "
            "Explore page (or type your town there), then ask again - or "
            "name a place, e.g. \"waterfalls near Tenkasi\"."
        )

    if intent == "festival":
        knowledge = search_knowledge(
            message
        )

        if knowledge:
            return knowledge

        return (
            "Tamil Nadu has many cultural and religious "
            "festivals. You can search for a specific "
            "festival or destination."
        )

    if intent == "budget":
        return (
            "I can help estimate your travel budget. "
            "Provide the number of travelers, trip "
            "duration and preferred budget level."
        )

    if intent == "itinerary":
        return (
            "I can create a Tamil Nadu itinerary based "
            "on your destinations, trip duration, "
            "interests and budget."
        )

    knowledge = search_knowledge(message)

    if knowledge:
        return knowledge

    place = get_place_information(search_term)

    if place:
        place = dict(place)
        return (
            f"{place.get('place_name', 'This destination')} "
            f"is located in "
            f"{place.get('district', 'Tamil Nadu')}. "
            f"{place.get('description', '')}"
        )

    return (
        "I can help you with Tamil Nadu tourism. "
        "You can ask me about tourist places, temples, "
        "beaches, festivals, nearby destinations, "
        "itineraries or travel budgets."
    )


def generate_ai_response(message):
    """AI-phrased reply grounded in the deterministic response above.

    The rule-based `generate_response` already does the real lookups
    (places, budgets, status, festivals); Groq only rewrites that factual
    text conversationally. If Groq is not configured or the call fails,
    the deterministic text is returned unchanged so the chatbot behaves
    identically with or without an API key.
    """

    grounding = generate_response(message)

    if not is_ai_enabled():
        return grounding

    ai_text = generate_ai_text(
        CONVERSATIONAL_SYSTEM_PROMPT,
        build_conversational_prompt(message, grounding),
    )

    return ai_text or grounding
