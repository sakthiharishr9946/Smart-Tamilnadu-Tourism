"""Free OpenStreetMap gazetteer for locating places that have no coordinates.

Most destinations still missing coordinates are HR&CE temples whose record
carries the village or town they stand in ("Arulmigu Porkodiamman Temple,
Vallandaramam"). Nominatim answers one name per second and rarely knows
those temples, so instead this module downloads - once per district, cached
on disk - every named settlement and every named place of worship that
OpenStreetMap has inside the district boundary, and matches locally:

1. the temple itself among the places of worship near its village
   -> precision "exact";
2. otherwise the village / town centre -> precision "locality" (good enough
   for maps and "near me", and labelled as approximate in the UI).
"""

import difflib
import logging
import math
import re
import time

from scrapers.http_client import HttpClient
from scrapers.opendata import OSM_CACHE_DIR, _post_overpass, _read_json, _write_json, discover_osm_districts
from services.data_quality import name_key

logger = logging.getLogger(__name__)

GAZETTEER_DIR = OSM_CACHE_DIR / "gazetteer"
GAZETTEER_MAX_AGE_SECONDS = 30 * 24 * 3600

# Two queries per district: settlements are small nodes and answer in
# seconds; places of worship are thousands of ways and are the part an
# overloaded Overpass server may time out on - then villages still work.
_SETTLEMENTS_QUERY = """[out:json][timeout:120];
area(id:{area_id})->.d;
node["place"~"^(city|town|village|hamlet|suburb|neighbourhood|quarter|locality)$"]["name"](area.d);
out body qt;"""

_WORSHIP_QUERY = """[out:json][timeout:180];
area(id:{area_id})->.d;
nwr["amenity"="place_of_worship"]["name"](area.d);
out center tags qt;"""

_NAME_TAGS = ("name:en", "name", "alt_name", "old_name", "official_name", "name:ta-Latn")
# Settlement kinds, most significant first: on a name clash a town beats a hamlet.
_PLACE_RANK = {"city": 0, "town": 1, "suburb": 2, "village": 3, "quarter": 4, "neighbourhood": 5,
               "hamlet": 6, "locality": 7}

# Words that say "this is a temple" without identifying which one.
_TEMPLE_WORDS = {
    "temple", "temples", "kovil", "koil", "kovill", "thirukoil", "thirukkoil", "tirukoil", "alayam", "devasthanam",
    "swamy", "swami", "samy", "sami", "swamigal", "sannidhi", "sannathi", "arulmigu", "sri", "shri", "shree", "sree",
    "thiru", "tiru", "the", "and", "of", "at", "new", "old", "big", "small", "periya", "chinna",
    "koyil", "koovil", "kooyil", "thirukkoovil", "aalayam", "devalayam",
}

TEMPLE_MATCH_THRESHOLD = 0.86
TEMPLE_UNANCHORED_THRESHOLD = 0.93
TEMPLE_ANCHOR_RADIUS_KM = 6.0
LOCALITY_SPREAD_KM = 12.0
SETTLEMENT_MATCH_THRESHOLD = 0.92


# Tamil script -> Latin, the way Tamil Nadu place names are usually spelt
# ("வேலப்பாடி" -> "velappaadi"). Many OSM villages carry only a Tamil name.
_TAMIL_VOWELS = {"அ": "a", "ஆ": "aa", "இ": "i", "ஈ": "ii", "உ": "u", "ஊ": "uu", "எ": "e", "ஏ": "e",
                 "ஐ": "ai", "ஒ": "o", "ஓ": "o", "ஔ": "au"}
_TAMIL_CONSONANTS = {"க": "k", "ங": "ng", "ச": "s", "ஞ": "nj", "ட": "d", "ண": "n", "த": "th", "ந": "n",
                     "ப": "p", "ம": "m", "ய": "y", "ர": "r", "ல": "l", "வ": "v", "ழ": "zh", "ள": "l",
                     "ற": "r", "ன": "n", "ஜ": "j", "ஷ": "sh", "ஸ": "s", "ஹ": "h", "ஶ": "sh"}
_TAMIL_SIGNS = {"ா": "aa", "ி": "i", "ீ": "ii", "ு": "u", "ூ": "uu", "ெ": "e", "ே": "e", "ை": "ai",
                "ொ": "o", "ோ": "o", "ௌ": "au", "்": ""}
_TAMIL_RE = re.compile(r"[஀-௿]")
# Spellings differ in voicing (Nagar/Nakar, Tiruvadi/Tiruvati); compare without it.
_VOICING = str.maketrans({"g": "k", "b": "p", "d": "t", "j": "s"})


def transliterate_tamil(text):
    out = []
    chars = str(text or "")
    for index, char in enumerate(chars):
        if char in _TAMIL_CONSONANTS:
            following = chars[index + 1] if index + 1 < len(chars) else ""
            out.append(_TAMIL_CONSONANTS[char] + ("" if following in _TAMIL_SIGNS else "a"))
        elif char in _TAMIL_SIGNS:
            out.append(_TAMIL_SIGNS[char])
        else:
            out.append(_TAMIL_VOWELS.get(char, char))
    return "".join(out)


def _phonetic(text):
    from preprocessing.merging import phonetic_key  # local import: avoids a merging <-> scrapers cycle
    if _TAMIL_RE.search(str(text or "")):
        text = transliterate_tamil(text)
    key = phonetic_key(name_key(text)).replace("ch", "s").translate(_VOICING)
    return re.sub(r"(.)\1+", r"\1", key)


def core_name_key(name):
    """Identifying part of a temple name: "Arulmigu Subramaniya Swamy Temple" -> "subramaniya"."""
    global _TEMPLE_KEYS
    if _TEMPLE_KEYS is None:
        _TEMPLE_KEYS = {_phonetic(word) for word in _TEMPLE_WORDS}
    return " ".join(token for token in _phonetic(name).split() if token not in _TEMPLE_KEYS)


_TEMPLE_KEYS = None


def split_locality(place_name, city_town=None, district=None):
    """(name, localities) - most specific locality first.

    "X Temple, Velapadi, Vellore" -> ("X Temple", ["Velapadi", "Vellore"]).
    The stored city_town follows the name's own parts, and the district's
    name (usually also its headquarters town) is only the last resort.
    """
    head, _, rest = str(place_name or "").partition(",")
    candidates = [part.strip() for part in [*rest.split(","), city_town or ""] if part and part.strip()]
    district_key = str(district or "").casefold()
    ordered = [p for p in candidates if p.casefold() != district_key] + \
              [p for p in candidates if p.casefold() == district_key]
    localities = []
    for part in ordered:
        if part.casefold() not in {existing.casefold() for existing in localities}:
            localities.append(part)
    return head.strip(), localities


_FEATURE_WORDS_RE = re.compile(
    r"\b(beach|temple|kovil|koil|dam|park|falls|waterfalls?|lake|reservoir|fort|church|mosque|dargah|museum|"
    r"memorial|hills?|view ?point|sanctuary|boat ?house|river|island|gardens?|point|tank|palace|shrine|"
    r"mandapam|manimandapam|light ?house|bird|wildlife|national|eco|tourism|spot|and)\b|&",
    re.IGNORECASE,
)


def name_localities(name, strip_features=True):
    """Village names hidden in a destination name, most specific first."""
    name = str(name or "")
    found = [match.group(1) for match in re.finditer(r"\b(?:at|near|in)\s+([A-Z][\w .'-]+)$", name)]
    found.append(name)  # "Alagar Kovil" == village "Alagarkovil"
    stripped = " ".join(_FEATURE_WORDS_RE.sub(" ", name).split())
    if strip_features and stripped and stripped != name:
        found.append(stripped)  # "Poompuhar Beach" -> "Poompuhar"
    return found


def _settlement_key(text):
    """Space-insensitive phonetic key for a village name ("Periya Kancheepuram" == "Periyakanchipuram")."""
    text = re.sub(r"\(.*?\)|\b(village|town|post|taluk|po)\b", " ", str(text or ""), flags=re.IGNORECASE)
    return _phonetic(text).replace(" ", "")


def haversine_km(lat1, lon1, lat2, lon2):
    lat1, lon1, lat2, lon2 = map(math.radians, (lat1, lon1, lat2, lon2))
    a = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 6371.0 * 2 * math.asin(min(1.0, math.sqrt(a)))


def compact_elements(elements):
    """Overpass elements -> small cache rows {kind, rank, lat, lon, keys}."""
    rows = []
    for element in elements:
        tags = element.get("tags") or {}
        lat = element.get("lat", (element.get("center") or {}).get("lat"))
        lon = element.get("lon", (element.get("center") or {}).get("lon"))
        if lat is None or lon is None:
            continue
        names = {tags[tag] for tag in _NAME_TAGS if tags.get(tag)}
        names |= {part.strip() for tag in ("alt_name", "old_name") for part in str(tags.get(tag, "")).split(";")}
        names = sorted(n for n in names if n and (re.search(r"[A-Za-z]", n) or _TAMIL_RE.search(n)))
        if not names:
            continue
        if tags.get("amenity") == "place_of_worship":
            rows.append({"kind": "worship", "lat": lat, "lon": lon, "names": names,
                         "religion": tags.get("religion")})
        elif tags.get("place") in _PLACE_RANK:
            rows.append({"kind": "settlement", "rank": _PLACE_RANK[tags["place"]], "lat": lat, "lon": lon,
                         "names": names})
    return rows


class DistrictGazetteer:
    """Settlements and places of worship of one district, indexed for matching."""

    def __init__(self, rows):
        self.settlements = {}
        self.worship = []
        for row in rows:
            if row["kind"] == "settlement":
                for name in row["names"]:
                    key = _settlement_key(name)
                    if key:
                        self.settlements.setdefault(key, []).append(row)
            else:
                cores = {core_name_key(name) for name in row["names"]}
                cores.discard("")
                if cores:
                    self.worship.append((sorted(cores), row))
        self._settlement_keys = list(self.settlements)

    def find_settlements(self, locality, fuzzy=True):
        key = _settlement_key(locality)
        if len(key) < 3:
            return []
        if key in self.settlements:
            return self.settlements[key]
        if not fuzzy:
            return []
        # Spelling variants only ("Kaniyambadi" / "Kaniyambādi"), never a
        # different village that merely sounds alike: same first letter, 92%.
        close = difflib.get_close_matches(key, self._settlement_keys, n=3, cutoff=SETTLEMENT_MATCH_THRESHOLD)
        return [row for match in close if match[0] == key[0] for row in self.settlements[match]]

    def find_temple(self, name, anchors):
        core = core_name_key(name)
        if len(core) < 4:
            return None
        if anchors:
            pool = [(cores, row) for cores, row in self.worship
                    if any(haversine_km(a["lat"], a["lon"], row["lat"], row["lon"]) <= TEMPLE_ANCHOR_RADIUS_KM
                           for a in anchors)]
            threshold = TEMPLE_MATCH_THRESHOLD
        else:
            pool, threshold = self.worship, TEMPLE_UNANCHORED_THRESHOLD
        scored = []
        for cores, row in pool:
            score = max(difflib.SequenceMatcher(None, core, candidate).ratio() for candidate in cores)
            if score >= threshold:
                scored.append((score, row))
        if not scored:
            return None
        scored.sort(key=lambda item: -item[0])
        best_score, best = scored[0]
        if not anchors:
            # Without a village to anchor on, the name alone must be unambiguous.
            rivals = [row for score, row in scored[1:] if score >= best_score - 0.02
                      and haversine_km(row["lat"], row["lon"], best["lat"], best["lon"]) > 1.0]
            if rivals:
                return None
        return best

    def locate(self, place_name, city_town=None, is_temple=True, district=None, exact_only=False):
        """(lat, lon, precision, matched_name) or None.

        ``exact_only`` disables fuzzy village matching (used when searching a
        neighbouring district, where a near-miss is more likely a different village).
        """
        name, localities = split_locality(place_name, city_town, district)
        anchors = []
        for locality in localities:
            anchors = self.find_settlements(locality, fuzzy=not exact_only)
            if anchors:
                break
        if not anchors:
            # The village is often part of the name itself: "Poompuhar Beach",
            # "Alagar Kovil" (village Alagarkovil), "X Memorial at Kanniyakumari".
            # A temple's name minus "Temple" is usually its deity, and deities
            # are also village names ("Kailasanathar"), so temples only use
            # the whole name or an explicit "at <village>".
            for candidate in name_localities(name, strip_features=not is_temple):
                if len(_settlement_key(candidate)) >= 5:
                    anchors = self.find_settlements(candidate, fuzzy=False)
                    if anchors:
                        break
        if is_temple:
            temple = self.find_temple(name, anchors)
            if temple:
                return temple["lat"], temple["lon"], "exact", temple["names"][0]
        if not anchors:
            return None
        anchors = sorted(anchors, key=lambda row: row["rank"])
        first = anchors[0]
        # Same village name in two corners of the district: ambiguous, skip.
        if any(haversine_km(first["lat"], first["lon"], a["lat"], a["lon"]) > LOCALITY_SPREAD_KM for a in anchors):
            return None
        return first["lat"], first["lon"], "locality", first["names"][0]


def _cached_rows(client, path, query, max_age, log, label, download=True):
    """Cached compact rows for one query, downloading when stale. None on failure."""
    if path.exists() and (not download or time.time() - path.stat().st_mtime < max_age):
        rows = _read_json(path)
        if rows is not None:
            return rows
    if not download:
        return None
    try:
        started = time.monotonic()
        payload = _post_overpass(client, query)
        rows = compact_elements(payload.get("elements", []))
        GAZETTEER_DIR.mkdir(parents=True, exist_ok=True)
        _write_json(path, rows)
        log(f"    {label}: {len(rows)} names in {time.monotonic() - started:.0f}s")
        return rows
    except Exception as error:  # noqa: BLE001 - one district never stops the rest
        rows = _read_json(path)
        log(f"    {label}: Overpass unavailable ({str(error)[:70]})" + (", using older copy" if rows else ""))
        return rows


def load_gazetteers(districts, client=None, max_age=GAZETTEER_MAX_AGE_SECONDS, log=print,
                    extra_rows=None, download=True):
    """{district: DistrictGazetteer} from OSM (plus ``extra_rows`` per district).

    ``extra_rows`` - e.g. GeoNames villages - is merged with whatever OSM has.
    With ``download=False`` only OSM data already cached is used (public
    Overpass servers can take minutes per district when busy). A district
    whose places-of-worship download fails still gets its settlements; the
    next run retries the missing part.
    """
    extra_rows = extra_rows or {}
    client = client or HttpClient(min_interval=2.0, timeout=(15, 200), retries=0)
    # District boundaries practically never change; skip the slow discovery
    # query when the OSM collector has already saved them.
    cached = _read_json(OSM_CACHE_DIR / "districts.json")
    relations = {d: int(r) for d, r in cached.items()} if cached else {}
    if not relations and download:
        relations = discover_osm_districts(client)
    gazetteers = {}
    for district in districts:
        rows = list(extra_rows.get(district) or [])
        relation = relations.get(district)
        if relation is not None:
            area_id = 3600000000 + int(relation)
            if download:
                log(f"  {district}")
            for suffix, query, label in (("places", _SETTLEMENTS_QUERY, "villages/towns"),
                                         ("worship", _WORSHIP_QUERY, "places of worship")):
                rows += _cached_rows(client, GAZETTEER_DIR / f"{relation}_{suffix}.json",
                                     query.format(area_id=area_id), max_age, log, label, download) or []
        if rows:
            gazetteers[district] = DistrictGazetteer(rows)
    return gazetteers
