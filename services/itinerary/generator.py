from datetime import datetime, timedelta


def _parse(value, fallback):
    try:
        return datetime.strptime(value, "%H:%M")
    except (TypeError, ValueError):
        return datetime.strptime(fallback, "%H:%M")


def _duration(place):
    try:
        value = int(float(place.get("avg_visit_duration", place.get("average_visit_duration", 120))))
    except (TypeError, ValueError):
        value = 120
    return max(30, value)


def generate_itinerary(places, days=1, start_time="09:00", end_time="17:00", daily_hours=8, break_minutes=30):
    if not places:
        return []
    try:
        days = max(1, int(days))
        break_minutes = max(0, int(break_minutes))
    except (TypeError, ValueError):
        return []

    start = _parse(start_time, "09:00")
    finish = _parse(end_time, "17:00")
    if finish <= start:
        finish += timedelta(days=1)

    remaining = [dict(p) for p in places]
    itinerary = []

    for day in range(1, days + 1):
        current = start
        schedule = []
        while remaining:
            place = remaining[0]
            duration = _duration(place)
            proposed_end = current + timedelta(minutes=duration)
            if proposed_end > finish:
                break
            remaining.pop(0)
            schedule.append({
                "order": len(schedule) + 1,
                "place": place,
                "start_time": current.strftime("%H:%M"),
                "end_time": proposed_end.strftime("%H:%M"),
                "duration_minutes": duration,
            })
            current = proposed_end + timedelta(minutes=break_minutes)

        itinerary.append({
            "day": day,
            "schedule": schedule,
            "total_hours": round(sum(x["duration_minutes"] for x in schedule) / 60, 2),
        })
        if not remaining:
            break

    # Keep the return type compatible with the existing UI; leftovers are stored on the final day.
    if itinerary:
        itinerary[-1]["remaining_places"] = remaining
    return itinerary


def create_day_schedule(places, start_time="09:00", end_time="17:00"):
    return generate_itinerary(places, days=1, start_time=start_time, end_time=end_time)[0].get("schedule", [])
