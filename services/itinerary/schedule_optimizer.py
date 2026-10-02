from datetime import datetime, timedelta


DEFAULT_START_TIME = "09:00"
DEFAULT_BREAK_MINUTES = 30


def parse_time(time_value):
    try:
        return datetime.strptime(
            time_value,
            "%H:%M",
        )
    except (TypeError, ValueError):
        return datetime.strptime(
            DEFAULT_START_TIME,
            "%H:%M",
        )


def get_visit_duration(place):
    duration = place.get(
        "average_visit_duration",
        120,
    )

    try:
        duration = int(float(duration))
    except (TypeError, ValueError):
        duration = 120

    return max(30, duration)


def optimize_daily_schedule(
    places,
    start_time=DEFAULT_START_TIME,
    break_minutes=DEFAULT_BREAK_MINUTES,
):
    if not places:
        return []

    current_time = parse_time(start_time)

    try:
        break_minutes = max(0, int(break_minutes))
    except (TypeError, ValueError):
        break_minutes = DEFAULT_BREAK_MINUTES

    schedule = []

    for index, place in enumerate(places, start=1):
        place_data = dict(place)

        duration = get_visit_duration(
            place_data
        )

        end_time = current_time + timedelta(
            minutes=duration
        )

        schedule.append(
            {
                "order": index,
                "place": place_data,
                "start_time": current_time.strftime(
                    "%H:%M"
                ),
                "end_time": end_time.strftime(
                    "%H:%M"
                ),
                "duration_minutes": duration,
            }
        )

        current_time = end_time + timedelta(
            minutes=break_minutes
        )

    return schedule


def optimize_multi_day_schedule(
    itinerary,
    start_time=DEFAULT_START_TIME,
    break_minutes=DEFAULT_BREAK_MINUTES,
):
    if not itinerary:
        return []

    optimized_itinerary = []

    for day_data in itinerary:
        places = day_data.get(
            "places",
            [],
        )

        places_only = []

        for item in places:
            if isinstance(item, dict) and "place" in item:
                places_only.append(item["place"])
            else:
                places_only.append(item)

        schedule = optimize_daily_schedule(
            places_only,
            start_time,
            break_minutes,
        )

        optimized_itinerary.append(
            {
                "day": day_data.get(
                    "day",
                    len(optimized_itinerary) + 1,
                ),
                "schedule": schedule,
                "total_places": len(schedule),
            }
        )

    return optimized_itinerary