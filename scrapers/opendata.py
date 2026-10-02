"""Collectors for OpenStreetMap (Overpass) and Wikidata.

These are the coordinate backbone of the dataset: government sources publish
names and descriptions, while OSM and Wikidata supply precise locations,
identifiers and freely licensed images.

Both collectors discover the 38 districts dynamically (OSM boundary relations
at ``admin_level=5`` inside ``ISO3166-2=IN-TN``; Wikidata items that are an
instance of "district of India" located in Tamil Nadu) and then query each
district separately, so one slow or failing district never loses the rest.
"""

import json
import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

from config.districts import TN_DISTRICTS
from config.settings import DATA_DIR
from scrapers.http_client import HttpClient, SourceUnavailable, short_error
from scrapers.parsing import classify_category, make_place, records_frame as _frame
from services.data_quality import resolve_district

logger = logging.getLogger(__name__)

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
OVERPASS_FALLBACK_URLS = (
    "https://overpass.private.coffee/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
)
OVERPASS_FALLBACK_URL = OVERPASS_FALLBACK_URLS[-1]
WIKIDATA_URL = "https://query.wikidata.org/sparql"
COMMONS_FILE_URL = "https://commons.wikimedia.org/wiki/Special:FilePath/"
OSM_CACHE_DIR = Path(DATA_DIR) / "cache" / "osm"
OSM_CACHE_MAX_AGE_SECONDS = 7 * 24 * 3600

# ---------------------------------------------------------------------------
# OpenStreetMap
# ---------------------------------------------------------------------------

_OSM_DISTRICTS_QUERY = """[out:json][timeout:120];
area["ISO3166-2"="IN-TN"]["admin_level"="4"]->.tn;
rel(area.tn)["boundary"="administrative"]["admin_level"="5"];
out tags;"""

# A few broad statements are much cheaper for Overpass than many narrow ones
# (a 16-statement union timed out after 240s; this shape answers in seconds).
# Common features - places of worship, parks, memorials - are kept only when
# notable (see ``_osm_is_destination``), otherwise every village shrine and
# street park in the state would become an "attraction".
_OSM_DISTRICT_QUERY = """[out:json][timeout:180];
area(id:{area_id})->.d;
(
  nwr["tourism"~"^(attraction|museum|gallery|viewpoint|zoo|theme_park|aquarium)$"]["name"](area.d);
  nwr["historic"]["name"](area.d);
  nwr["natural"~"^(waterfall|peak|beach|cave_entrance|hot_spring|cape|bay)$"]["name"](area.d);
  nwr["waterway"="waterfall"]["name"](area.d);
  nwr["leisure"~"^(nature_reserve|water_park)$"]["name"](area.d);
  nwr["boundary"="national_park"]["name"](area.d);
  nwr["man_made"="lighthouse"]["name"](area.d);
  nwr["wikidata"]["name"](area.d);
);
out center tags qt;"""

_OSM_CORE_HISTORIC = {"fort", "castle", "palace", "ruins", "archaeological_site", "monument", "tomb",
                      "city_gate", "temple", "cave", "rock_shelter", "heritage"}


def _osm_is_destination(tags):
    """Tourism features always count; common features need a notability signal."""
    tourism = (tags.get("tourism") or "").casefold()
    historic = (tags.get("historic") or "").casefold()
    if tourism in {"attraction", "museum", "gallery", "viewpoint", "zoo", "theme_park", "aquarium"}:
        return True
    if historic in _OSM_CORE_HISTORIC:
        return True
    if (tags.get("natural") or "") in {"waterfall", "peak", "beach", "cave_entrance", "hot_spring", "cape", "bay"}:
        return True
    if tags.get("waterway") == "waterfall" or tags.get("boundary") == "national_park":
        return True
    if (tags.get("leisure") or "") in {"nature_reserve", "water_park"} or tags.get("man_made") == "lighthouse":
        return True
    notable = bool(tags.get("wikidata") or tags.get("wikipedia") or tags.get("heritage"))
    if not notable:
        return False
    return bool(
        tags.get("amenity") == "place_of_worship"
        or historic
        or (tags.get("leisure") or "") in {"park", "garden"}
        or (tags.get("natural") or "") in {"water", "wetland"}
        or tags.get("waterway") == "dam"
    )


_OSM_EXCLUDED_TOURISM = {"hotel", "guest_house", "hostel", "motel", "information", "office", "apartment", "chalet"}


def _osm_category(tags, name):
    tourism = (tags.get("tourism") or "").casefold()
    natural = (tags.get("natural") or "").casefold()
    historic = (tags.get("historic") or "").casefold()
    leisure = (tags.get("leisure") or "").casefold()
    amenity = (tags.get("amenity") or "").casefold()
    religion = (tags.get("religion") or "").casefold()
    if amenity == "place_of_worship" or historic == "temple":
        if religion in {"hindu", "jain", "buddhist", ""}:
            return "Temple"
        return "Cultural"
    if natural == "waterfall" or tags.get("waterway") == "waterfall":
        return "Waterfall"
    if natural in {"beach", "cape", "bay"}:
        return "Beach"
    if tourism in {"zoo", "aquarium"} or tags.get("boundary") == "national_park":
        return "Wildlife"
    if leisure == "nature_reserve":
        return classify_category(name, default="Wildlife")
    if natural == "peak":
        return "Hill"
    if historic in {"fort", "castle", "palace", "ruins", "archaeological_site", "city_gate", "cave", "rock_shelter"}:
        return "Historical"
    if tourism in {"museum", "gallery"} or historic in {"monument", "memorial", "tomb", "heritage", "building", "manor"}:
        return "Heritage"
    if tags.get("man_made") == "lighthouse":
        return "Heritage"
    if tourism == "theme_park" or leisure == "water_park":
        return "Adventure"
    if natural in {"cave_entrance", "hot_spring", "water", "wetland"} or leisure in {"park", "garden"} or tags.get("waterway") == "dam":
        return "Nature"
    return classify_category(name, tags.get("description"))


def _osm_image(tags):
    """A Commons image URL from OSM's image/wikimedia_commons tags, if any."""
    for key in ("wikimedia_commons", "image"):
        value = (tags.get(key) or "").strip()
        if value.startswith("File:"):
            return COMMONS_FILE_URL + value[5:].replace(" ", "_")
        if key == "image" and value.startswith("https://commons.wikimedia.org/wiki/File:"):
            return COMMONS_FILE_URL + value.split("File:", 1)[1]
        if key == "image" and value.startswith("https://upload.wikimedia.org/"):
            return value
    return None


# Names that describe an object type rather than a specific destination.
_OSM_GENERIC_WORDS = {
    "arch", "entrance", "gate", "statue", "memorial", "monument", "inscription", "inscriptions",
    "temple", "church", "mosque", "gallery", "viewpoint", "view", "point", "park", "pillar", "stone",
    "hero", "nandi", "shelter", "tank", "mandapam", "old", "new", "small", "big", "main", "the",
}


def _is_generic_osm_name(name):
    words = re.findall(r"[a-z]+", name.casefold())
    return len(words) <= 2 and all(word in _OSM_GENERIC_WORDS for word in words)


def parse_overpass_elements(elements, district):
    records = []
    for element in elements:
        tags = element.get("tags") or {}
        if (tags.get("tourism") or "").casefold() in _OSM_EXCLUDED_TOURISM or not _osm_is_destination(tags):
            continue
        name = tags.get("name:en") or tags.get("name")
        if not name or not re.search(r"[A-Za-z]", name):
            name = tags.get("int_name") or tags.get("name:en")
        if not name or _is_generic_osm_name(name):
            continue
        center = element.get("center") or {}
        latitude = element.get("lat", center.get("lat"))
        longitude = element.get("lon", center.get("lon"))
        if latitude is None or longitude is None:
            continue
        city = (tags.get("addr:city") or tags.get("addr:town") or tags.get("addr:village")
                or tags.get("addr:suburb") or tags.get("is_in:city"))
        notable = bool(tags.get("wikidata") or tags.get("wikipedia"))
        image = _osm_image(tags)
        record = make_place(
            name, district, f"https://www.openstreetmap.org/{element.get('type')}/{element.get('id')}",
            category_name=_osm_category(tags, name),
            subcategory=(tags.get("tourism") or tags.get("historic") or tags.get("natural")
                         or tags.get("leisure") or tags.get("amenity") or tags.get("man_made")),
            description=tags.get("description:en") or tags.get("description"),
            latitude=latitude, longitude=longitude, city=city, address=tags.get("addr:full"),
            wikidata_id=tags.get("wikidata"), osm_id=f"{element.get('type')}/{element.get('id')}",
            image_url=image, image_source="Wikimedia Commons" if image else None,
            tourism_relevance=0.8 if notable else 0.6,
        )
        if record:
            records.append(record)
    return records


def _post_overpass(client, query, endpoints=None, deadline=None):
    last_error = None
    for endpoint in endpoints or (OVERPASS_URL, *OVERPASS_FALLBACK_URLS):
        if deadline is not None and last_error is not None and time.monotonic() > deadline:
            break  # do not start another slow endpoint after the time budget
        try:
            response = client.post(endpoint, data={"data": query})
            payload = response.json()
            remark = str(payload.get("remark") or "")
            if "runtime error" in remark.casefold():
                raise requests.RequestException(remark[:200])
            return payload
        except (requests.RequestException, ValueError) as error:
            last_error = error
            logger.info("Overpass endpoint %s failed: %s", endpoint, short_error(error))
    raise last_error if last_error else SourceUnavailable("No Overpass endpoint configured")


_OSM_RELATIONS_FROM_WIKIDATA_QUERY = """SELECT ?districtLabel ?osm WHERE {
  ?district wdt:P31 wd:Q1149652; wdt:P131 wd:Q1445; wdt:P402 ?osm.
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
}"""


def _read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _write_json(path, data):
    try:
        OSM_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(json.dumps(data), encoding="utf-8")
    except OSError as error:
        logger.warning("Could not write cache %s: %s", path, error)


def discover_osm_districts(client):
    """{canonical district: OSM relation id} for the 38 TN districts.

    Boundary relations practically never change, so the last answer is kept
    on disk. Order of preference: Overpass, then that cache, then the OSM
    relation ids Wikidata records for each district (property P402).
    """
    cache_path = OSM_CACHE_DIR / "districts.json"
    try:
        payload = _post_overpass(client, _OSM_DISTRICTS_QUERY)
        districts = {}
        for element in payload.get("elements", []):
            tags = element.get("tags") or {}
            district = resolve_district(tags.get("name:en") or tags.get("name"))
            if district and district not in districts:
                districts[district] = element["id"]
        if districts:
            _write_json(cache_path, districts)
            return districts
    except Exception as error:
        logger.info("Overpass district discovery failed (%s); using fallbacks", short_error(error))

    cached = _read_json(cache_path)
    if cached:
        return {district: int(relation) for district, relation in cached.items()}

    districts = {}
    for row in _sparql(client, _OSM_RELATIONS_FROM_WIKIDATA_QUERY):
        district = resolve_district((row.get("districtLabel") or {}).get("value"))
        relation = (row.get("osm") or {}).get("value", "")
        if district and relation.isdigit() and district not in districts:
            districts[district] = int(relation)
    if districts:
        _write_json(cache_path, districts)
    return districts


def _cached_overpass(client, district, relation_id, max_age, deadline=None):
    """District payload: fresh cache, else Overpass, else stale cache.

    Returns (payload, origin) where origin is "cache", "live" or "stale".
    """
    path = OSM_CACHE_DIR / f"{relation_id}.json"
    is_fresh = path.exists() and time.time() - path.stat().st_mtime < max_age
    if max_age and is_fresh:
        cached = _read_json(path)
        if cached is not None:
            return cached, "cache"
    try:
        payload = _post_overpass(client, _OSM_DISTRICT_QUERY.format(area_id=3600000000 + int(relation_id)),
                                 deadline=deadline)
    except Exception:
        stale = _read_json(path)
        if stale is not None:
            return stale, "stale"
        raise
    _write_json(path, {"elements": payload.get("elements", [])})
    return payload, "live"


OSM_TIME_BUDGET_SECONDS = 25 * 60


def scrape_openstreetmap_tourism_by_district(districts=None, client=None, timeout=None, pause_seconds=1.0,
                                             max_workers=2, cache_max_age=OSM_CACHE_MAX_AGE_SECONDS,
                                             time_budget=OSM_TIME_BUDGET_SECONDS):
    """Named tourism POIs inside each Tamil Nadu district boundary.

    Overpass serves two concurrent queries per client, so districts are
    fetched two at a time. Each district's raw response is cached on disk
    for ``cache_max_age`` seconds (pass 0 to force fresh data).

    Public Overpass servers are frequently overloaded. Once ``time_budget``
    seconds have passed, districts not yet fetched fall back to older cached
    data or are skipped with a warning; because every completed district is
    cached, the next run continues where this one stopped.
    """
    del timeout  # kept for backwards compatibility; the client owns timeouts
    # Overpass queries carry their own 180 s server timeout; a read timeout a
    # little above it with one retry per endpoint bounds the worst case.
    client = client or HttpClient(min_interval=pause_seconds, timeout=(15, 200), retries=1, backoff=10)
    try:
        relations = discover_osm_districts(client)
    except Exception as error:
        raise SourceUnavailable(f"Overpass unavailable: {short_error(error)}") from error
    if not relations:
        raise SourceUnavailable("Overpass returned no Tamil Nadu district boundaries")

    requested = list(districts or TN_DISTRICTS)
    targets = [d for d in requested if d in relations]
    warnings = [f"No OSM boundary found for {d}" for d in requested if d not in relations]

    deadline = time.monotonic() + time_budget if time_budget else None

    def fetch(district):
        try:
            if deadline is not None and time.monotonic() > deadline:
                stale = _read_json(OSM_CACHE_DIR / f"{relations[district]}.json")
                if stale is None:
                    raise SourceUnavailable("time budget exhausted; will be fetched on the next run")
                payload, origin = stale, "stale"
            else:
                payload, origin = _cached_overpass(client, district, relations[district], cache_max_age, deadline)
            return district, parse_overpass_elements(payload.get("elements", []), district), origin, None
        except Exception as error:
            return district, [], None, error

    records, district_counts = [], {}
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        for district, district_records, origin, error in pool.map(fetch, targets):
            district_counts[district] = len(district_records)
            if error is not None:
                warnings.append(f"{district}: {short_error(error)}")
                continue
            if origin == "stale":
                warnings.append(f"{district}: Overpass unavailable, used older cached data")
            records.extend(district_records)
            logger.info("OSM %s: %d places (%s)", district, len(district_records), origin)
    if not records:
        raise SourceUnavailable("Overpass returned no tourism features: " + "; ".join(warnings[:3]))
    return _frame(records, warnings, district_counts=district_counts)


def scrape_openstreetmap_tourism(timeout=None, client=None, **options):
    """All 38 districts; ``options`` are passed to ``scrape_openstreetmap_tourism_by_district``."""
    return scrape_openstreetmap_tourism_by_district(client=client, timeout=timeout, **options)


# ---------------------------------------------------------------------------
# Wikidata
# ---------------------------------------------------------------------------

_WIKIDATA_DISTRICTS_QUERY = """SELECT ?district ?districtLabel WHERE {
  ?district wdt:P31 wd:Q1149652; wdt:P131 wd:Q1445.
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
}"""

_WIKIDATA_PLACES_QUERY = """SELECT ?place ?placeLabel ?placeDescription ?coord
       (GROUP_CONCAT(DISTINCT ?typeLabel; separator="|") AS ?types)
       (SAMPLE(?image) AS ?img) (SAMPLE(?article) AS ?wiki)
       (GROUP_CONCAT(DISTINCT ?alias; separator="|") AS ?aliases) WHERE {
  ?place wdt:P131+ wd:%s; wdt:P625 ?coord; wdt:P31 ?type.
  ?type rdfs:label ?typeLabel. FILTER(LANG(?typeLabel) = "en")
  OPTIONAL { ?place wdt:P18 ?image }
  OPTIONAL { ?article schema:about ?place; schema:isPartOf <https://en.wikipedia.org/> }
  OPTIONAL { ?place skos:altLabel ?alias. FILTER(LANG(?alias) = "en") }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
}
GROUP BY ?place ?placeLabel ?placeDescription ?coord"""

# An item is kept when one of its types matches TOURISM and none matches
# EXCLUDED (bank branches, schools, villages and the like dominate raw results).
_WIKIDATA_TOURISM_TYPES = re.compile(
    r"temple|mosque|church|basilica|cathedral|dargah|shrine|gurdwara|synagogue|beach|waterfall|"
    r"\bhill\b|hill station|mountain|peak|zoo|wildlife|sanctuary|national park|tiger reserve|biosphere|"
    r"\blake\b|reservoir|\bdam\b|garden|\bpark\b|museum|monument|memorial|fort|palace|heritage|"
    r"archaeological|rock-cut|cave|tourist attraction|lighthouse|island|backwater|mangrove|wetland|"
    r"gopuram|mandapam|stupa|tomb|mausoleum|statue|rock art|ramsar|world heritage|viewpoint|"
    r"protected area|reserve forest|amusement park|theme park|aquarium|planetarium",
    re.IGNORECASE)
_WIKIDATA_EXCLUDED_TYPES = re.compile(
    r"bank|branch|school|college|university|institute|hospital|clinic|station|gas station|village|"
    r"human settlement|neighbo(u)?rhood|constituency|panchayat|taluk|block|ward|company|business|"
    r"organization|organisation|office|airport|road|street|bridge|hotel|restaurant|shop|mall|"
    r"cinema|stadium|cemetery|census town|municipality|city|town|electoral|polling",
    re.IGNORECASE)


def _sparql(client, query):
    response = client.get(WIKIDATA_URL, params={"query": query, "format": "json"},
                          headers={"Accept": "application/sparql-results+json"})
    return response.json().get("results", {}).get("bindings", [])


def discover_wikidata_districts(client):
    """{canonical district: QID} for Tamil Nadu's districts."""
    districts = {}
    for row in _sparql(client, _WIKIDATA_DISTRICTS_QUERY):
        district = resolve_district(row.get("districtLabel", {}).get("value"))
        qid = row.get("district", {}).get("value", "").rsplit("/", 1)[-1]
        if district and qid and district not in districts:
            districts[district] = qid
    return districts


def _commons_url(value):
    # P18 values come back as http://commons.wikimedia.org/wiki/Special:FilePath/<name>
    if not value:
        return None
    return value.replace("http://", "https://", 1)


def parse_wikidata_rows(rows, district):
    records = []
    for row in rows:
        value = lambda key: (row.get(key) or {}).get("value")
        types = value("types") or ""
        if not _WIKIDATA_TOURISM_TYPES.search(types):
            continue
        if any(_WIKIDATA_EXCLUDED_TYPES.search(t) and not _WIKIDATA_TOURISM_TYPES.search(t) for t in types.split("|")):
            continue
        name = value("placeLabel")
        qid = (value("place") or "").rsplit("/", 1)[-1]
        if not name or re.fullmatch(r"Q\d+", name):  # no English label
            continue
        match = re.match(r"Point\(([-\d.]+) ([-\d.]+)\)", value("coord") or "")
        if not match:
            continue
        longitude, latitude = match.groups()
        image = _commons_url(value("img"))
        record = make_place(
            name, district, value("wiki") or f"https://www.wikidata.org/wiki/{qid}",
            category_name=classify_category(name, types, default=None) or classify_category(types),
            subcategory=types.split("|")[0][:80], description=value("placeDescription"),
            latitude=latitude, longitude=longitude, wikidata_id=qid,
            image_url=image, image_source="Wikimedia Commons" if image else None,
            tourism_relevance=0.9 if value("wiki") else 0.7, aliases=value("aliases"),
        )
        if record:
            records.append(record)
    return records


def scrape_wikidata_tourism(timeout=None, client=None, max_workers=3):
    """Geocoded tourism items located (transitively) in each TN district."""
    del timeout  # kept for backwards compatibility; the client owns timeouts
    client = client or HttpClient(min_interval=0.3, timeout=(10, 90), retries=3, backoff=3)
    try:
        districts = discover_wikidata_districts(client)
    except Exception as error:
        raise SourceUnavailable(f"Wikidata unavailable: {short_error(error)}") from error
    if not districts:
        raise SourceUnavailable("Wikidata returned no Tamil Nadu districts")

    def fetch(item):
        district, qid = item
        try:
            return district, parse_wikidata_rows(_sparql(client, _WIKIDATA_PLACES_QUERY % qid), district), None
        except Exception as error:
            return district, [], error

    records, warnings = [], [f"No Wikidata item for {d}" for d in TN_DISTRICTS if d not in districts]
    # WDQS allows at most 5 parallel queries per client; stay well below it.
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        for district, district_records, error in pool.map(fetch, districts.items()):
            if error is not None:
                warnings.append(f"{district}: {short_error(error)}")
                continue
            records.extend(district_records)
            logger.info("Wikidata %s: %d places", district, len(district_records))
    if not records:
        raise SourceUnavailable("Wikidata returned no tourism items: " + "; ".join(warnings[:3]))
    return _frame(_resolve_multi_district_items(records), warnings)


def _resolve_multi_district_items(records):
    """Keep one district per Wikidata item.

    Items with several "located in" chains (a lake listed under a hill town
    and a neighbouring revenue division, say) are returned by more than one
    district query. The right district is the one whose unambiguous places
    lie closest to the item.
    """
    by_item = {}
    for record in records:
        by_item.setdefault(record["wikidata_id"], []).append(record)
    ambiguous = {qid for qid, group in by_item.items() if len({r["district"] for r in group}) > 1}
    if not ambiguous:
        return records

    def located(record):
        return record["latitude"] is not None and record["longitude"] is not None

    centres = {}
    for record in records:
        if record["wikidata_id"] not in ambiguous and located(record):
            centres.setdefault(record["district"], []).append((record["latitude"], record["longitude"]))
    centres = {
        district: (sorted(p[0] for p in points)[len(points) // 2], sorted(p[1] for p in points)[len(points) // 2])
        for district, points in centres.items()
    }

    def distance(record):
        centre = centres.get(record["district"])
        if not centre or not located(record):
            return float("inf")
        return (record["latitude"] - centre[0]) ** 2 + (record["longitude"] - centre[1]) ** 2

    resolved = [r for r in records if r["wikidata_id"] not in ambiguous]
    for qid in ambiguous:
        resolved.append(min(by_item[qid], key=distance))
    return resolved
