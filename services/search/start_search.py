"""The GPS-first Start Searching application flow."""

from database.queries import get_all_places, record_search_history
from config.search_config import MAX_RADIUS_KM
from services.nearby.adaptive_search import adaptive_search
from services.nearby.distance import add_distance_to_places, sort_by_distance
from services.recommendation.scoring import score_places
from services.status.place_status import add_status_to_places


def start_search(latitude, longitude, interests=None, min_results=10):
    """Find, distance-rank, and status-rank destinations near a user."""
    places = [dict(place) for place in get_all_places()]
    if not places:
        try:
            from services.data_updates import refresh_tourism_data
            refresh_tourism_data(skip=("osm",))
            places = [dict(place) for place in get_all_places()]
        except Exception:
            return [], {"radius_km": None, "message": "Tourism data could not be refreshed. Try again later."}
    if not places:
        return [], {"radius_km": None, "message": "Tourism data is not available yet."}
    nearby, radius = adaptive_search(places, latitude, longitude, min_results=min_results)
    message = "Nearby destinations ranked for you."
    if not nearby:
        # Nothing within the maximum radius (e.g. the traveller is outside
        # Tamil Nadu): show the closest destinations rather than nothing.
        closest = sort_by_distance(add_distance_to_places(places, latitude, longitude))
        nearby = [place for place in closest if place.get("distance_km") is not None][:min_results]
        if not nearby:
            return [], {"radius_km": None, "message": "No destinations with map locations are available yet."}
        radius = round(nearby[-1]["distance_km"])
        message = f"No destinations within {MAX_RADIUS_KM} km of you - these are the closest."
    nearby = add_status_to_places(nearby)
    interest_scores = {
        item.get("place_id"): item.get("interest_score", 0.0)
        for item in nearby
    }
    scored = score_places(nearby, interest_scores=interest_scores)
    scored.sort(key=lambda item: item.get("recommendation_score", 0), reverse=True)
    record_search_history("GPS search", latitude, longitude, 10, radius, len(scored))
    return scored, {"radius_km": radius, "message": message}
