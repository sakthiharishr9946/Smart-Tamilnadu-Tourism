"""Current, time-sensitive tourist-place status helpers."""

from datetime import datetime, timezone

import requests

from database.queries import get_latest_place_status, upsert_place_status


UNSUITABLE_TERMS = {"closed", "dry", "unsafe", "unavailable", "not suitable"}


def normalise_status(status):
    return " ".join(str(status or "Unknown").strip().split())


def status_suitability(status, explicit_score=None):
    if explicit_score is not None:
        try:
            return max(0.0, min(1.0, float(explicit_score)))
        except (TypeError, ValueError):
            pass
    text = normalise_status(status).lower()
    return 0.2 if any(term in text for term in UNSUITABLE_TERMS) else 1.0


def record_place_status(place_id, status, details="", source_url=None, source_id=None,
                        suitability_score=None, expires_at=None):
    """Store an observed status separately from permanent destination data."""
    return upsert_place_status(
        place_id=place_id,
        status=normalise_status(status),
        details=details,
        source_url=source_url,
        source_id=source_id,
        suitability_score=status_suitability(status, suitability_score),
        expires_at=expires_at,
    )


def get_current_status(place_id):
    row = get_latest_place_status(place_id)
    if not row:
        return {"status": "Status not recently verified", "suitability_score": 1.0,
                "checked_at": None, "is_fresh": False}
    result = dict(row)
    result["suitability_score"] = status_suitability(
        result.get("status"), result.get("suitability_score")
    )
    expires_at = result.get("expires_at")
    try:
        expiry = datetime.fromisoformat(str(expires_at).replace("Z", "+00:00"))
        if expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=timezone.utc)
        result["is_fresh"] = expiry >= datetime.now(timezone.utc)
    except (TypeError, ValueError):
        result["is_fresh"] = False
    return result


def add_status_to_places(places):
    results = []
    for place in places or []:
        item = dict(place)
        item["current_status"] = get_current_status(item.get("place_id"))
        item["status_suitability"] = item["current_status"]["suitability_score"]
        results.append(item)
    return results


def refresh_status_from_source(place_id, source_url, source_name="Destination status source", timeout=15):
    """Record a source-verified status page without overwriting permanent place data.

    Source pages are intentionally supplied per destination: not every tourism
    source publishes reliable real-time conditions, so this avoids guessing.
    """
    response = requests.get(source_url, timeout=timeout, headers={"User-Agent": "SmartTamilnaduTourism/1.0"})
    response.raise_for_status()
    text = " ".join(response.text.lower().split())
    if any(term in text for term in ("closed", "closure", "dry", "unsafe")):
        status, score = "Currently unsuitable", 0.2
    else:
        status, score = "No unsuitable condition reported", 1.0
    return record_place_status(
        place_id, status, details=f"Checked from {source_name}", source_url=source_url,
        suitability_score=score,
    )
