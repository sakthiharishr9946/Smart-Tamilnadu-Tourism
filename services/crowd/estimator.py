"""Heuristic crowd-level estimate used until real crowd_data is collected.

The ML pipeline in models/crowd_prediction expects a trained model built
from historical crowd_data, but that table has no rows yet, so there is
nothing to train on. This estimator reuses the same classify_crowd()
thresholds with a hand-tuned score based on weekday, season, festivals and
destination category, so the crowd indicator shows a reasonable estimate
instead of nothing.
"""

from datetime import date, datetime

from services.crowd.classification import classify_crowd

# Nov-Feb is Tamil Nadu's peak tourist season (cooler weather).
PEAK_SEASON_MONTHS = {11, 12, 1, 2}

CATEGORY_CROWD_WEIGHT = {
    "temple": 0.20,
    "beach": 0.20,
    "hill": 0.15,
    "heritage": 0.10,
    "historical": 0.10,
    "cultural": 0.10,
    "waterfall": 0.10,
    "wildlife": 0.05,
    "nature": 0.05,
}


def _is_same_day(festival_date, visit_date):
    if not festival_date:
        return False

    try:
        parsed = datetime.strptime(str(festival_date)[:10], "%Y-%m-%d").date()
    except ValueError:
        return False

    return parsed == visit_date


def _festival_month(festival):
    if festival.get("start_date"):
        return None  # dated festivals are matched by day above
    try:
        return int(festival.get("month"))
    except (TypeError, ValueError):
        return None


def estimate_crowd_score(category_name, visit_date=None, festivals=None):
    visit_date = visit_date or date.today()
    festivals = festivals or []

    score = 0.15

    if visit_date.weekday() >= 5:
        score += 0.25

    if visit_date.month in PEAK_SEASON_MONTHS:
        score += 0.15

    # Festival rows carry an exact start_date (state holidays) or only a
    # month (district festivals such as "Chithirai Festival (April/May)").
    if any(_is_same_day(festival.get("start_date") or festival.get("festival_date"), visit_date)
           for festival in festivals):
        score += 0.25
    elif any(_festival_month(festival) == visit_date.month for festival in festivals):
        score += 0.10

    score += CATEGORY_CROWD_WEIGHT.get(str(category_name or "").strip().lower(), 0.0)

    return max(0.0, min(1.0, score))


def estimate_crowd_level(category_name, visit_date=None, festivals=None):
    score = estimate_crowd_score(category_name, visit_date, festivals)
    return classify_crowd(score), score
