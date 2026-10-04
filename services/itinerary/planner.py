"""Realistic day-by-day trip planning.

The planner turns a starting place and a set of destinations into days a
traveller could actually follow:

* Days stay geographically compact. Destinations are put in driving order
  from the start (nearest-neighbour, then 2-opt to remove crossings) and
  each day takes the next stretch of that route, so one day never jumps
  between opposite ends of a district.
* Every visit respects when that kind of place is open and worth visiting:
  temples in the morning or after 4 pm (most Tamil Nadu temples close
  around 12:30-4 pm), wildlife, dams and waterfalls in daylight (done by
  6 pm), museums and forts in the middle of the day, beaches in the morning
  or evening. Within a day the stop order is chosen to fit those windows
  with the least driving and waiting.
* Driving time between stops, a lunch break, and visit lengths that suit
  each kind of place are part of the timeline.
* The starting place is the first stop of day 1.
"""

from itertools import permutations

from services.nearby.distance import calculate_distance

# Straight-line distance x ROAD_FACTOR ~ road distance on Tamil Nadu roads.
ROAD_FACTOR = 1.3
AVERAGE_SPEED_KMH = 40
PARKING_MINUTES = 10
UNKNOWN_LEG_MINUTES = 30        # a stop without map coordinates
MAX_LEG_MINUTES = 150           # never plan a single drive longer than this
MAX_STOPS_PER_DAY = 6
DAY_SPAN_KM = 60                # no two stops of one day further apart than this
CANDIDATES_PER_STEP = 8         # nearest candidates tried when growing a day
SEEDS_PER_DAY = 5               # areas tried as the first stop of a new day
FIRST_LEG_MAX_MINUTES = 240     # the morning drive to a new area may be long
MAX_WAIT_MINUTES = 270          # arriving at noon and waiting for a 4 pm temple reopening is fine
LUNCH_FROM, LUNCH_UNTIL, LUNCH_MINUTES = 12 * 60 + 30, 14 * 60 + 30, 45
NOT_PREFERRED_PENALTY = 40      # minutes-equivalent cost of a less ideal (but open) slot


def _hm(text):
    hours, minutes = str(text).split(":")[:2]
    return int(hours) * 60 + int(minutes)


def _clock(minutes):
    minutes = int(round(minutes))
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


# kind -> (open windows, preferred windows, default visit minutes, timing note)
_PROFILES = {
    "temple": ([("05:30", "12:30"), ("16:00", "21:00")], [("05:30", "11:00"), ("17:00", "20:30")], 75,
               "Temples are usually closed from about 12:30 to 4 pm"),
    "wildlife": ([("06:00", "18:00")], [("06:00", "11:00"), ("15:00", "18:00")], 150,
                 "Wildlife is easiest to see in the morning; parks close by 6 pm"),
    "waterfall": ([("07:00", "18:00")], [("07:00", "16:00")], 90, "Outdoor spot - visit in daylight"),
    "nature": ([("07:00", "18:00")], [("07:00", "11:30"), ("15:00", "18:00")], 75, "Outdoor spot - visit in daylight"),
    "hill": ([("06:00", "18:30")], [("06:00", "11:30"), ("15:00", "18:30")], 120, "Viewpoints are best early or late"),
    "beach": ([("05:30", "20:00")], [("05:30", "09:30"), ("16:00", "19:30")], 90,
              "Beaches are pleasant in the morning or evening"),
    "heritage": ([("09:00", "17:30")], [("10:00", "16:00")], 75, "Museums and monuments keep daytime hours"),
    "historical": ([("09:00", "17:30")], [("10:00", "16:00")], 75, "Monuments keep daytime hours"),
    "cultural": ([("06:00", "20:30")], [("08:00", "19:30")], 45, ""),
    "adventure": ([("10:00", "18:00")], [("10:00", "17:00")], 180, "Parks and activities keep daytime hours"),
}
_DEFAULT_PROFILE = ([("08:00", "19:00")], [("09:00", "18:00")], 60, "")


def place_profile(place):
    """(open windows, preferred windows, visit minutes, note) in minutes since midnight."""
    category = str(place.get("category_name") or place.get("category") or "").strip().casefold()
    name = str(place.get("place_name") or "").casefold()
    kind = category if category in _PROFILES else None
    # Name hints refine broad categories ("Aliyar Dam" is Nature, "Museum" is Heritage).
    if kind in (None, "nature", "cultural") and any(w in name for w in ("dam", "reservoir", "falls", "park")):
        kind = "waterfall" if "falls" in name else "nature"
    if any(w in name for w in ("museum", "gallery", "palace", "mahal")):
        kind = "heritage"
    windows, preferred, minutes, note = _PROFILES.get(kind, _DEFAULT_PROFILE)
    try:
        stored = int(float(place.get("avg_visit_duration") or 0))
    except (TypeError, ValueError):
        stored = 0
    return ([(_hm(a), _hm(b)) for a, b in windows], [(_hm(a), _hm(b)) for a, b in preferred],
            stored if stored >= 20 else minutes, note)


def _kind(place):
    category = str(place.get("category_name") or place.get("category") or "").strip().casefold()
    name = str(place.get("place_name") or "").casefold()
    if any(w in name for w in ("museum", "gallery", "palace", "mahal")):
        return "museum"
    return category


def timing_note(place, start_minute):
    """One friendly line on why this stop sits at this time of day."""
    kind, hour = _kind(place), start_minute / 60
    morning, evening = hour < 12, hour >= 16
    if kind == "temple":
        if morning:
            return "A morning darshan, before the temple closes for the afternoon."
        if evening:
            return "Timed for the evening, after the temple reopens at 4 pm - the evening pooja is worth staying for."
        return "Temple hours vary - many close around 12:30-4 pm, so check locally."
    if kind == "wildlife":
        return ("Early hours are the best time to spot animals." if morning
                else "Parks close by 6 pm, so this visit wraps up before dusk.")
    if kind in ("waterfall", "nature", "hill"):
        return ("Cooler in the morning, and the light is lovely for photos." if morning
                else "A daylight visit - outdoor spots like this are best before 6 pm.")
    if kind in ("museum", "heritage", "historical"):
        return "Mostly indoors or shaded - a good way to spend the hottest part of the day." if 11 <= hour < 16             else "Monuments keep daytime hours, so this fits well here."
    if kind == "beach":
        return ("The beach is at its best in the evening breeze." if evening
                else "Mornings here are calm and cool.")
    return ""


def _coords(place):
    try:
        lat, lon = float(place.get("latitude")), float(place.get("longitude"))
    except (TypeError, ValueError):
        return None
    return lat, lon


def drive(a, b):
    """(road km or None, minutes) between two places (or coordinate tuples)."""
    first = a if isinstance(a, tuple) else (_coords(a) if a else None)
    second = b if isinstance(b, tuple) else (_coords(b) if b else None)
    if not first or not second:
        return None, UNKNOWN_LEG_MINUTES
    km = calculate_distance(first[0], first[1], second[0], second[1]) * ROAD_FACTOR
    if km < 0.3:
        return round(km, 1), 0
    minutes = km / AVERAGE_SPEED_KMH * 60 + PARKING_MINUTES
    return round(km, 1), int(5 * round(minutes / 5))


# ---------------------------------------------------------------------------
# Route order
# ---------------------------------------------------------------------------

def route_order(places, start=None):
    """Destinations in driving order from ``start`` (nearest-neighbour + 2-opt).

    Places without coordinates go last, in their given order.
    """
    located = [p for p in places if _coords(p)]
    unlocated = [p for p in places if not _coords(p)]
    origin = _coords(start) if start else None
    order, here = [], origin
    remaining = list(located)
    while remaining:
        if here is None:
            nxt = remaining[0]
        else:
            nxt = min(remaining, key=lambda p: calculate_distance(here[0], here[1], *_coords(p)))
        remaining.remove(nxt)
        order.append(nxt)
        here = _coords(nxt)

    def leg(a, b):
        return calculate_distance(a[0], a[1], b[0], b[1]) if a and b else 0.0

    # 2-opt: reverse any stretch that shortens the route (start fixed).
    points = [origin] + [_coords(p) for p in order]
    improved = True
    while improved and len(order) > 2:
        improved = False
        for i in range(1, len(points) - 2):
            for j in range(i + 1, len(points) - 1):
                if leg(points[i - 1], points[j]) + leg(points[i], points[j + 1]) + 1e-9 < \
                        leg(points[i - 1], points[i]) + leg(points[j], points[j + 1]):
                    points[i:j + 1] = reversed(points[i:j + 1])
                    order[i - 1:j] = reversed(order[i - 1:j])
                    improved = True
    return order + unlocated


# ---------------------------------------------------------------------------
# One day
# ---------------------------------------------------------------------------

def _simulate(stops, origin, day_start, day_end, lunch=True):
    """Timeline for visiting ``stops`` in order, or None when it does not fit.

    Returns (entries, cost). Cost = driving + waiting + penalties for
    visiting outside a place's preferred hours.
    """
    now, here, cost, entries, lunched = day_start, origin, 0.0, [], not lunch
    for index, place in enumerate(stops):
        windows, preferred, minutes, _ = place_profile(place)
        # The very first stop of a trip with no known origin needs no drive.
        km, travel = (None, 0) if (here is None and index == 0) else drive(here, place)
        # The morning's first drive may be long (moving on to a new area); later hops may not.
        if travel > (FIRST_LEG_MAX_MINUTES if index == 0 else MAX_LEG_MINUTES):
            return None
        # Break for lunch before moving on, once it is lunchtime.
        if not lunched and LUNCH_FROM <= now < LUNCH_UNTIL:
            entries.append({"kind": "lunch", "start_minute": now, "end_minute": now + LUNCH_MINUTES})
            now += LUNCH_MINUTES
            lunched = True
        arrive = now + travel
        slot = None
        for opens, closes in windows:
            begin = max(arrive, opens)
            if begin + minutes <= closes:
                slot = begin
                break
        if slot is None or slot - arrive > MAX_WAIT_MINUTES:
            return None
        finish = slot + minutes
        if finish > day_end:
            return None
        wait = slot - arrive
        # Waiting through lunchtime (e.g. for a temple to reopen at 4 pm):
        # have lunch during the wait - after the drive, before the visit.
        lunch_start, lunch_during_wait = max(arrive, LUNCH_FROM), None
        if not lunched and lunch_start < LUNCH_UNTIL and lunch_start + LUNCH_MINUTES <= slot:
            lunch_during_wait = {"start_time": _clock(lunch_start),
                                 "end_time": _clock(lunch_start + LUNCH_MINUTES)}
            lunched = True
            wait -= LUNCH_MINUTES
        in_preferred = any(begin <= slot and slot + minutes <= end for begin, end in preferred)
        # Long idle time is allowed when nothing else fits, but costs more
        # than the same time spent driving or at a less ideal hour.
        cost += travel + 0.6 * wait + (0 if in_preferred else NOT_PREFERRED_PENALTY)
        entries.append({
            "kind": "visit", "place": place, "start_minute": slot, "end_minute": finish,
            "duration_minutes": minutes, "travel_km": km, "travel_minutes": travel,
            "wait_minutes": wait, "note": timing_note(place, slot), "preferred_slot": in_preferred,
            "lunch_before": lunch_during_wait,
        })
        now, here = finish, _coords(place) or here
    return entries, cost


def _best_day(stops, origin, day_start, day_end, fixed_first=None):
    """Cheapest feasible visiting order for one day (exhaustive for small days)."""
    free = [p for p in stops if p is not fixed_first]
    best = None
    candidates = permutations(free) if len(free) <= 7 else [tuple(free)]
    for order in candidates:
        sequence = ([fixed_first] if fixed_first is not None else []) + list(order)
        result = _simulate(sequence, origin, day_start, day_end)
        if result and (best is None or result[1] < best[1]):
            best = result
    return best


# ---------------------------------------------------------------------------
# Whole trip
# ---------------------------------------------------------------------------

def plan_trip(places, start_place=None, days=1, start_time="09:00", end_time="18:00"):
    """Plan a trip.

    Returns {"days": [{"day", "entries", "drive_km", "drive_minutes"}],
             "unscheduled": [places], "total_km": float}.
    ``entries`` are dicts with kind "visit" (place, start_time, end_time,
    duration_minutes, travel_km, travel_minutes, note, is_start) or "lunch".
    """
    try:
        days = max(1, int(days))
    except (TypeError, ValueError):
        days = 1
    day_start, day_end = _hm(start_time), _hm(end_time)
    if day_end <= day_start:
        day_end = day_start + 8 * 60

    start_id = (start_place or {}).get("place_id")
    seen, unique = set(), []
    for place in places or []:
        key = place.get("place_id") or place.get("place_name")
        if key in seen or (start_id is not None and place.get("place_id") == start_id):
            continue
        seen.add(key)
        unique.append(dict(place))

    # Places whose hours never overlap the travel day can never be planned.
    unscheduled = [p for p in unique if _best_day([p], _coords(p), day_start, day_end) is None]
    remaining = [p for p in route_order(unique, start_place) if p not in unscheduled]
    origin = _coords(start_place) if start_place else None
    plan_days = []

    for day_number in range(1, days + 1):
        fixed = dict(start_place, is_start=True) if (start_place and day_number == 1) else None
        chosen = [fixed] if fixed else []
        best = _best_day(chosen, origin, day_start, day_end, fixed_first=fixed) if fixed else None
        if fixed and best is None:
            # The start is always visited first, whatever its hours.
            minutes = place_profile(fixed)[2]
            best = ([{"kind": "visit", "place": fixed, "start_minute": day_start,
                      "end_minute": day_start + minutes, "duration_minutes": minutes, "travel_km": None,
                      "travel_minutes": 0, "wait_minutes": 0, "note": timing_note(fixed, day_start),
                      "preferred_slot": False}], 0)

        if fixed:
            chosen, grown = _grow_day(chosen, remaining, origin, day_start, day_end, fixed)
            best = grown or best
        else:
            # Try the nearest few areas to head for and keep the fullest day
            # (then the one with least driving), so one far-off stop never
            # takes a whole day while a cluster of sights waits elsewhere.
            anchors = [origin] if origin else []
            seeds = sorted(remaining, key=lambda p: _nearest_km(p, anchors))[:SEEDS_PER_DAY]
            options = []
            for seed in seeds:
                if _best_day([seed], origin, day_start, day_end) is None:
                    continue
                day_stops, grown = _grow_day([seed], [p for p in remaining if p is not seed],
                                             origin, day_start, day_end, None)
                if grown:
                    drive_minutes = sum(e.get("travel_minutes") or 0 for e in grown[0] if e["kind"] == "visit")
                    options.append((-len(day_stops), drive_minutes, day_stops, grown))
            if options:
                _, _, chosen, best = min(options, key=lambda item: (item[0], item[1]))
            for place in chosen:
                if place in remaining:
                    remaining.remove(place)
        if best is None:
            continue
        entries = best[0]
        for entry in entries:
            entry["start_time"] = _clock(entry["start_minute"])
            entry["end_time"] = _clock(entry["end_minute"])
            if entry["kind"] == "visit":
                entry["is_start"] = bool(entry["place"].get("is_start"))
        visits = [e for e in entries if e["kind"] == "visit"]
        plan_days.append({
            "day": len(plan_days) + 1,
            "entries": entries,
            "drive_km": round(sum(e["travel_km"] or 0 for e in visits), 1),
            "drive_minutes": sum(e["travel_minutes"] or 0 for e in visits),
        })
        # Stay overnight near the day's last stop.
        last = next((_coords(e["place"]) for e in reversed(visits) if _coords(e["place"])), None)
        origin = last or origin
        if not remaining:
            break

    unscheduled += remaining
    return {
        "days": plan_days,
        "unscheduled": unscheduled,
        "total_km": round(sum(day["drive_km"] for day in plan_days), 1),
    }


def _grow_day(chosen, remaining, origin, day_start, day_end, fixed):
    """Add the nearest stops that still fit the day (all within DAY_SPAN_KM).

    Returns (stops, best timeline) and removes added stops from ``remaining``.
    """
    chosen, best = list(chosen), _best_day(chosen, origin, day_start, day_end, fixed_first=fixed)
    while remaining and len(chosen) < MAX_STOPS_PER_DAY + (1 if fixed else 0):
        anchors = [c for c in (_coords(p) for p in chosen) if c] or ([origin] if origin else [])
        options = sorted((p for p in remaining if _fits_span(p, chosen)), key=lambda p: _nearest_km(p, anchors))
        for candidate in options[:CANDIDATES_PER_STEP]:
            attempt = _best_day(chosen + [candidate], origin, day_start, day_end, fixed_first=fixed)
            if attempt:
                chosen.append(candidate)
                remaining.remove(candidate)
                best = attempt
                break
        else:
            break
    return chosen, best


def _nearest_km(place, anchors):
    """Straight-line km from ``place`` to the closest anchor (far away when unknown)."""
    here = _coords(place)
    if not here or not anchors:
        return 10_000.0
    return min(calculate_distance(here[0], here[1], a[0], a[1]) for a in anchors)


def _fits_span(place, chosen):
    """True when ``place`` is within DAY_SPAN_KM of every located stop of the day."""
    here = _coords(place)
    if not here:
        return True
    return all(calculate_distance(here[0], here[1], *c) <= DAY_SPAN_KM
               for c in (_coords(p) for p in chosen) if c)
