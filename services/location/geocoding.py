from typing import Optional, Tuple

from geopy.geocoders import Nominatim


_GEOCODER = Nominatim(
    user_agent="smart_tamilnadu_tourism"
)


def geocode_location(
    location_name: str,
) -> Optional[Tuple[float, float]]:
    if not location_name or not location_name.strip():
        return None

    try:
        location = _GEOCODER.geocode(
            f"{location_name}, Tamil Nadu, India",
            timeout=10,
        )

        if location is None:
            return None

        return float(location.latitude), float(location.longitude)

    except Exception:
        return None


def reverse_geocode(
    latitude: float,
    longitude: float,
) -> Optional[str]:
    try:
        location = _GEOCODER.reverse(
            (latitude, longitude),
            exactly_one=True,
            timeout=10,
        )

        if location is None:
            return None

        return location.address

    except Exception:
        return None


# Nominatim's structured address doesn't always have "city" — fall back
# through the field a small settlement is actually tagged with.
_CITY_ADDRESS_FIELDS = (
    "city",
    "town",
    "municipality",
    "village",
    "suburb",
    "county",
)


def reverse_geocode_place(
    latitude: float,
    longitude: float,
) -> Optional[dict]:
    """Return {"city": ..., "district": ...} for a coordinate, or None."""
    try:
        location = _GEOCODER.reverse(
            (latitude, longitude),
            exactly_one=True,
            timeout=10,
            addressdetails=True,
        )

        if location is None:
            return None

        address = location.raw.get("address", {})

        city = next(
            (
                address[field]
                for field in _CITY_ADDRESS_FIELDS
                if address.get(field)
            ),
            None,
        )

        district = (
            address.get("state_district")
            or address.get("county")
            or address.get("state")
        )

        if not city and not district:
            return None

        return {"city": city, "district": district}

    except Exception:
        return None

def geocode_in_district(query: str, district: str) -> Optional[Tuple[float, float]]:
    """Geocode ``query`` and accept the result only if it lies in ``district``.

    Free-text geocoding of common names ("Mariamman Temple, Puthur") often
    lands in a same-named village elsewhere in the state; checking the
    returned district rejects those instead of pinning the place wrongly.
    Callers must respect Nominatim's limit of one request per second.
    """
    from services.data_quality import resolve_district

    if not query or not query.strip() or not district:
        return None
    try:
        location = _GEOCODER.geocode(
            f"{query}, Tamil Nadu, India",
            timeout=10,
            addressdetails=True,
            country_codes="in",
        )
    except Exception:
        return None
    if location is None:
        return None
    address = location.raw.get("address", {})
    found = resolve_district(address.get("state_district")) or resolve_district(address.get("county"))
    if found != resolve_district(district):
        return None
    return float(location.latitude), float(location.longitude)
