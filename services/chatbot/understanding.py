"""Extract the district and tourism category a chat message is about.

"Best waterfalls near Tenkasi?" -> district Tenkasi, category Waterfall.
Only "near me" / "around me" style phrases mean the traveller's own
position; "near <district>" names a district.
"""

import re

from config.districts import TN_DISTRICTS
from services.data_quality import TN_DISTRICT_ALIASES

# Keyword stems -> application category (TOURISM_CATEGORIES).
CATEGORY_KEYWORDS = (
    ("Waterfall", r"water\s?falls?|falls|aruvi|cascades?"),
    ("Beach", r"beach(?:es)?|sea\s?shore|coast(?:al|line)?"),
    ("Hill", r"hill\s?stations?|hills?|peaks?|mountains?|view\s?points?|trek(?:king)?\s?spots?"),
    ("Temple", r"temples?|kovils?|koils?|shrines? of|pilgrim(?:age)?"),
    ("Wildlife", r"wildlife|sanctuar(?:y|ies)|zoos?|national parks?|tiger reserves?|birds?(?: watching)?|safari"),
    ("Historical", r"forts?|palaces?|ruins|historical|history"),
    ("Heritage", r"heritage|museums?|monuments?|memorials?"),
    ("Adventure", r"adventure|boating|rafting|theme parks?|water parks?"),
    ("Nature", r"lakes?|dams?|parks?|gardens?|forests?|nature|backwaters?|mangroves?|eco"),
    ("Cultural", r"churches|church|mosques?|dargahs?|cultural|culture"),
)
_COMPILED = tuple((category, re.compile(rf"\b(?:{pattern})\b", re.IGNORECASE)) for category, pattern in CATEGORY_KEYWORDS)

_NEAR_ME_RE = re.compile(r"\b(near|around|close to|nearby)\s+(me|here|my location|us)\b|\bnearby\b(?!\s+\w)", re.IGNORECASE)

# Names a traveller might type, longest first so "the nilgiris" beats "nilgiris".
_DISTRICT_NAMES = sorted(
    {**{d.casefold(): d for d in TN_DISTRICTS}, **TN_DISTRICT_ALIASES,
     "ooty": "Nilgiris", "kodaikanal": "Dindigul", "kodai": "Dindigul", "madras": "Chennai",
     "mahabalipuram": "Chengalpattu", "mamallapuram": "Chengalpattu", "rameswaram": "Ramanathapuram",
     "courtallam": "Tenkasi", "kutralam": "Tenkasi", "yercaud": "Salem", "tanjore": "Thanjavur",
     "kumbakonam": "Thanjavur", "velankanni": "Nagapattinam", "hogenakkal": "Dharmapuri",
     "pondy": None, "pondicherry": None, "puducherry": None}.items(),
    key=lambda item: -len(item[0]),
)


def find_district(message):
    """Canonical district named (directly or via a well-known town) in the message."""
    text = (message or "").casefold()
    for name, district in _DISTRICT_NAMES:
        if district and re.search(rf"\b{re.escape(name)}\b", text):
            return district
    return None


def find_category(message):
    for category, pattern in _COMPILED:
        if pattern.search(message or ""):
            return category
    return None


def wants_near_me(message):
    return bool(_NEAR_ME_RE.search(message or ""))
