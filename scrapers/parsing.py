"""Parsing and normalisation helpers shared by every tourism scraper.

Each scraper produces "place records": plain dicts using the column names in
``PLACE_COLUMNS``. The helpers here make sure a record coming from any source
has a clean display name, a valid district, one of the application's tourism
categories and coordinates that really fall inside Tamil Nadu.
"""

import re
from html import unescape

import pandas as pd
from bs4 import BeautifulSoup

from config.categories import TOURISM_CATEGORIES
from config.constants import MAX_LATITUDE, MAX_LONGITUDE, MIN_LATITUDE, MIN_LONGITUDE
from config.districts import TN_DISTRICTS
from services.data_quality import is_educational_place, name_key, resolve_district  # noqa: F401 (re-export)

PLACE_COLUMNS = [
    "place_name", "district", "city", "category_name", "subcategory", "description",
    "latitude", "longitude", "address", "source_url", "wikidata_id", "osm_id",
    "image_url", "image_source", "image_license", "image_author", "tourism_relevance",
    "aliases",  # "|"-separated alternative names, used only for cross-source matching
]

# Navigation, widget and boilerplate text that government CMS templates
# render as links or headings. None of these is ever a destination.
JUNK_NAMES = {
    "home", "tourism", "tourist places", "tourist place", "places of interest", "place of interest",
    "tourist information", "how to reach", "photo gallery", "gallery", "media gallery", "video",
    "read more", "view all", "view more", "know more", "click here", "more", "select", "filter",
    "contact us", "about us", "about district", "feedback", "notices", "media corner", "directory",
    "site map", "sitemap", "social media links", "administrative setup", "downloads", "login",
    "register", "disclaimer", "copyright", "privacy policy", "terms", "terms and conditions",
    "help", "accessibility", "screen reader access", "skip to main content", "right to information",
    "events & festivals", "events and festivals", "festivals and events", "festivals & events",
    "accommodation", "accommodation (hotel/resort/dharamsala)", "nearby destinations",
    "category others", "others", "all", "by air", "by train", "by road", "destinations",
    "popular destinations", "where to go", "explore", "subscribe", "dams", "famous falls",
    "photo", "photos", "map", "location", "district map", "documents", "announcements",
}

JUNK_SUBSTRINGS = (
    "privacy", "disclaimer", "copyright", "skip to", "feedback", "website policies",
    "last updated", "visitor", "help desk", "©", "toll free", "opens in a new window",
    "share on", "subscribe to", "newsletter",
)

# Words that only ever appear in listing/category headings ("Parks and
# Gardens", "Temples", "Dams & Lakes") - a name made solely of these is a
# section title, not a destination.
GENERIC_HEADING_WORDS = {
    "and", "&", "of", "the", "in", "other", "others", "famous", "important", "popular", "major",
    "tourist", "tourism", "places", "spots", "attractions", "destinations", "sites", "centres", "centers",
    "parks", "gardens", "temples", "churches", "mosques", "dargahs", "beaches", "waterfalls", "falls",
    "dams", "lakes", "hills", "forts", "palaces", "museums", "monuments", "sanctuaries", "zoos",
    "pilgrim", "pilgrimage", "religious", "historical", "heritage", "nature", "wildlife", "eco", "list",
}

_SERIAL_PREFIX_RE = re.compile(r"^\s*\d{1,4}\s*[.)]\s*(?=\S)")
_TRAILING_JUNK_RE = re.compile(r"[\s→»›>|:,;\-–—]+$")
_TRAILING_PHRASE_RE = re.compile(r"\s*[-|:]?\s*(category\b.*|read more|view more|know more|click here)$", re.IGNORECASE)
_LATIN_RE = re.compile(r"[A-Za-z]")
_WS_RE = re.compile(r"\s+")

_DISTRICT_NAME_KEYS = {d.casefold() for d in TN_DISTRICTS}


def html_to_text(value):
    """Strip tags/entities from an HTML fragment and collapse whitespace."""
    if value is None:
        return ""
    text = str(value)
    if "<" in text:
        text = BeautifulSoup(text, "lxml").get_text(" ")
    return _WS_RE.sub(" ", unescape(text).replace(" ", " ")).strip()


def soup(html):
    return BeautifulSoup(html or "", "lxml")


def clean_place_name(value):
    """Return a display-ready destination name ('' when nothing usable)."""
    text = html_to_text(value)
    text = _SERIAL_PREFIX_RE.sub("", text)
    text = _TRAILING_PHRASE_RE.sub("", text)
    text = _TRAILING_JUNK_RE.sub("", text).strip(" .\"'")
    if text.isupper() and len(text) > 3:
        text = text.title()
    else:
        # "AYYANAR Kovil" -> "Ayyanar Kovil"; short acronyms (MGR, ISRO) stay.
        text = re.sub(r"\b[A-Z]{5,}\b", lambda m: m.group(0).title(), text)
    return text


def is_junk_place_name(name, district=None):
    """True for UI text, bare district names and other non-destinations."""
    if not name:
        return True
    low = name.casefold().strip()
    if len(low) < 3 or len(low) > 120 or not _LATIN_RE.search(name):
        return True
    if low in JUNK_NAMES or any(part in low for part in JUNK_SUBSTRINGS):
        return True
    if low.startswith(("http://", "https://", "www.", "stay at ", "stay in ")):
        return True
    if all(token in GENERIC_HEADING_WORDS for token in re.findall(r"[a-z&]+", low)):
        return True
    # "Madurai" or "Madurai District" on its own is a district/city page, not
    # an attraction inside it.
    bare = re.sub(r"\s+district$", "", low)
    if bare in _DISTRICT_NAME_KEYS or resolve_district(bare) == bare.title():
        return True
    if district and bare == str(district).casefold():
        return True
    return False


# Ordered: the first matching rule wins, so specific signals ("temple") are
# checked before generic ones ("hill"). Every value is a TOURISM_CATEGORIES name.
_CATEGORY_RULES = (
    ("Temple", r"\b(temple|kovil|koil|thirukoil|thirukkoil|perumal|amman|easwarar|eswarar|iswarar|"
               r"swamy|sannidhi|gopuram|mutt|math|ashram|jain temple|basadi)\b"),
    ("Cultural", r"\b(church|basilica|cathedral|shrine|mosque|masjid|dargah|darga|gurudwara|synagogue)\b"),
    ("Waterfall", r"\b(waterfalls?|falls|aruvi|cascade)\b"),
    ("Beach", r"\b(beach|seashore|sea shore)\b"),
    ("Wildlife", r"\b(sanctuary|wildlife|zoo|zoological|national park|tiger reserve|biosphere|"
                 r"bird|birds|elephant|safari|crocodile|deer park|aquarium)\b"),
    ("Historical", r"\b(fort|fortress|palace|mahal|ruins?|excavation|archaeolog\w*|rock[- ]cut|"
                   r"inscription|dolmen|megalithic|cave temple|caves?)\b"),
    ("Heritage", r"\b(museum|memorial|monument|mandapam|heritage|art gallery|lighthouse|light house|"
                 r"manimandapam|statue|tomb|samadhi|mausoleum|stupa|railway)\b"),
    ("Adventure", r"\b(trek|trekking|rafting|paragliding|boating|boat house|boathouse|adventure|"
                  r"theme park|water park|amusement|zipline|camping|climbing)\b"),
    ("Hill", r"\b(hills?|peak|view ?point|ghat|mountain|malai|betta|shola|summit|top station)\b"),
    ("Nature", r"\b(lake|dam|reservoir|park|garden|forest|eco|backwaters?|mangroves?|wetland|"
               r"river|island|valley|estuary|spring|botanical|tank|anicut)\b"),
)
_COMPILED_CATEGORY_RULES = tuple((category, re.compile(pattern, re.IGNORECASE)) for category, pattern in _CATEGORY_RULES)
assert all(category in TOURISM_CATEGORIES for category, _ in _CATEGORY_RULES)


def classify_category(*texts, default="Cultural"):
    """Pick a tourism category from names/descriptions/source hints."""
    text = " ".join(str(t) for t in texts if t)
    for category, pattern in _COMPILED_CATEGORY_RULES:
        if pattern.search(text):
            return category
    return default


def parse_coordinate(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number == number else None  # reject NaN


def valid_tn_coordinates(latitude, longitude):
    """Coordinates parsed to floats when they fall inside Tamil Nadu, else (None, None)."""
    lat, lon = parse_coordinate(latitude), parse_coordinate(longitude)
    if lat is None or lon is None:
        return None, None
    if MIN_LATITUDE <= lat <= MAX_LATITUDE and MIN_LONGITUDE <= lon <= MAX_LONGITUDE:
        return round(lat, 6), round(lon, 6)
    return None, None


def truncate(text, limit=600):
    text = html_to_text(text)
    if len(text) <= limit:
        return text or None
    cut = text[:limit].rsplit(" ", 1)[0].rstrip(",;:")
    return cut + "…"


def make_place(place_name, district, source_url, *, category_hint=None, **fields):
    """Build a validated place record, or None when it must be rejected.

    ``category_hint`` (e.g. "Waterfalls" from a listing page) is used together
    with the name to choose the category when ``category_name`` is not given.
    """
    name = clean_place_name(place_name)
    canonical_district = resolve_district(district)
    if not canonical_district or is_junk_place_name(name, canonical_district):
        return None
    latitude, longitude = valid_tn_coordinates(fields.pop("latitude", None), fields.pop("longitude", None))
    record: dict = {column: None for column in PLACE_COLUMNS}
    record.update({k: v for k, v in fields.items() if v not in ("", None)})
    record.update({
        "place_name": name,
        "district": canonical_district,
        "latitude": latitude,
        "longitude": longitude,
        "source_url": source_url,
    })
    if not record.get("category_name"):
        record["category_name"] = classify_category(name, category_hint, record.get("subcategory"))
    if record.get("description"):
        record["description"] = truncate(record["description"])
    if is_educational_place(record):
        return None
    return record


def records_frame(records, warnings=None, **attrs):
    """DataFrame of place records (deduplicated by name+district) with run metadata in ``attrs``."""
    frame = pd.DataFrame(records, columns=PLACE_COLUMNS) if records else pd.DataFrame(columns=PLACE_COLUMNS)
    if not frame.empty:
        frame = frame.drop_duplicates(subset=["place_name", "district"], keep="first").reset_index(drop=True)
    frame.attrs["warnings"] = list(warnings or [])
    for key, value in attrs.items():
        frame.attrs[key] = value
    return frame
