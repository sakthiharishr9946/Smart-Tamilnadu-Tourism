from datetime import date

from services.crowd.classification import classify_crowd
from services.crowd.estimator import estimate_crowd_level, estimate_crowd_score

WEEKDAY_OFF_SEASON = date(2026, 6, 10)   # Wednesday in June
WEEKEND_PEAK = date(2026, 12, 12)        # Saturday in December


def test_classification_thresholds():
    assert classify_crowd(0.1) == "Low"
    assert classify_crowd(0.5) == "Medium"
    assert classify_crowd(0.9) == "High"
    assert classify_crowd(1.5) == "Unknown"
    assert classify_crowd("not a number") == "Unknown"


def test_weekend_peak_season_is_busier():
    quiet = estimate_crowd_score("Nature", WEEKDAY_OFF_SEASON)
    busy = estimate_crowd_score("Nature", WEEKEND_PEAK)
    assert busy > quiet


def test_dated_festival_on_visit_day_raises_crowd():
    festivals = [{"festival_name": "Pongal", "start_date": "2026-06-10"}]
    without = estimate_crowd_score("Temple", WEEKDAY_OFF_SEASON)
    with_festival = estimate_crowd_score("Temple", WEEKDAY_OFF_SEASON, festivals)
    assert round(with_festival - without, 2) == 0.25


def test_month_only_district_festival_raises_crowd_less():
    festivals = [{"festival_name": "Avanimoolam Festival", "month": 6, "start_date": None}]
    without = estimate_crowd_score("Temple", WEEKDAY_OFF_SEASON)
    with_festival = estimate_crowd_score("Temple", WEEKDAY_OFF_SEASON, festivals)
    assert round(with_festival - without, 2) == 0.10


def test_score_is_bounded_and_level_matches():
    festivals = [{"start_date": "2026-12-12"}]
    level, score = estimate_crowd_level("Beach", WEEKEND_PEAK, festivals)
    assert 0.0 <= score <= 1.0
    assert level == classify_crowd(score) == "High"
