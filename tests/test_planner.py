from services.itinerary.planner import DAY_SPAN_KM, plan_trip
from services.nearby.distance import calculate_distance


def _p(pid, name, category, lat, lon):
    return {"place_id": pid, "place_name": name, "category_name": category, "latitude": lat, "longitude": lon}


# Coimbatore: Maruthamalai start, city temples, a museum, the far south (Pollachi side).
START = _p(1, "Maruthamalai Temple", "Temple", 11.046, 76.853)
KONIAMMAN = _p(2, "Koniamman Temple", "Temple", 10.994, 76.964)
EACHANARI = _p(3, "Eachanari Vinayagar Temple", "Temple", 10.924, 76.982)
MUSEUM = _p(4, "Gass Forest Museum", "Heritage", 11.014, 76.946)
ALIYAR = _p(5, "Aliyar Dam", "Nature", 10.472, 76.977)
MONKEY = _p(6, "Monkey Falls", "Waterfall", 10.460, 76.968)
PARK = _p(7, "Anamalai Tiger Reserve", "Wildlife", 10.348, 77.095)


def _minutes(clock):
    hours, minutes = clock.split(":")
    return int(hours) * 60 + int(minutes)


def _visits(plan):
    return [(day["day"], e) for day in plan["days"] for e in day["entries"] if e["kind"] == "visit"]


def test_start_place_is_first_stop_of_day_one_and_not_repeated():
    plan = plan_trip([START, KONIAMMAN, MUSEUM], START, days=1, start_time="09:00", end_time="19:00")
    visits = _visits(plan)
    assert visits[0][1]["place"]["place_name"] == "Maruthamalai Temple" and visits[0][1]["is_start"]
    assert [e["place"]["place_id"] for _, e in visits].count(1) == 1


def test_temples_avoid_the_afternoon_closure():
    plan = plan_trip([KONIAMMAN, EACHANARI, MUSEUM], START, days=1, start_time="09:00", end_time="20:00")
    for _, entry in _visits(plan):
        if entry["place"]["category_name"] == "Temple":
            start, end = _minutes(entry["start_time"]), _minutes(entry["end_time"])
            assert end <= 12 * 60 + 30 or start >= 16 * 60, entry


def test_outdoor_places_are_visited_in_daylight():
    plan = plan_trip([ALIYAR, MONKEY, PARK], START, days=3, start_time="09:00", end_time="21:00")
    for _, entry in _visits(plan):
        if not entry["is_start"]:
            assert _minutes(entry["end_time"]) <= 18 * 60, entry


def test_each_day_stays_in_one_area():
    plan = plan_trip([KONIAMMAN, EACHANARI, MUSEUM, ALIYAR, MONKEY, PARK], START, days=3,
                     start_time="09:00", end_time="19:00")
    for day in plan["days"]:
        stops = [e["place"] for e in day["entries"] if e["kind"] == "visit"]
        for a in stops:
            for b in stops:
                assert calculate_distance(a["latitude"], a["longitude"], b["latitude"], b["longitude"]) <= DAY_SPAN_KM
    planned = {e["place"]["place_id"] for _, e in _visits(plan)}
    assert {2, 3, 4, 5, 6, 7} <= planned  # three days are enough for everything


def test_places_that_do_not_fit_are_reported_not_forced_in():
    plan = plan_trip([KONIAMMAN, ALIYAR, MONKEY, PARK], START, days=1, start_time="09:00", end_time="19:00")
    planned = {e["place"]["place_id"] for _, e in _visits(plan)}
    unplanned = {p["place_id"] for p in plan["unscheduled"]}
    assert planned | unplanned == {1, 2, 5, 6, 7} and not planned & unplanned
    assert len(plan["days"]) == 1


def test_lunch_break_is_planned_on_a_full_day():
    plan = plan_trip([KONIAMMAN, EACHANARI, MUSEUM], START, days=1, start_time="09:00", end_time="19:00")
    entries = plan["days"][0]["entries"]
    assert any(e["kind"] == "lunch" or e.get("lunch_before") for e in entries)


def test_temple_after_a_long_drive_waits_for_the_evening_on_the_same_day():
    # Arriving around noon: lunch, then the temple when it reopens at 4 pm.
    fort = _p(10, "Alamparai Fort", "Historical", 12.268, 80.000)
    temple = _p(11, "Mukunda Nayanar Temple", "Temple", 12.617, 80.195)
    plan = plan_trip([temple], fort, days=2, start_time="09:00", end_time="19:00")
    assert len(plan["days"]) == 1
    visit = [e for e in plan["days"][0]["entries"] if e["kind"] == "visit"][-1]
    assert visit["start_time"] >= "16:00" and visit["lunch_before"]
