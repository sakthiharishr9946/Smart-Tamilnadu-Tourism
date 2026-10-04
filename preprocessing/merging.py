"""Cross-source merging of place records.

The same destination usually arrives from several sources: a district
portal (best name and description), TTDC (official description and photo),
OpenStreetMap/Wikidata (precise coordinates, identifiers, licensed images).
Records are grouped when they share a Wikidata item, an OSM element, or the
same normalised name in the same district - unless both have coordinates
more than ``MAX_SAME_PLACE_KM`` apart (two different "Murugan Temple"s).
Each group becomes one place that takes every field from the most
authoritative source that has it.
"""

import math

from services.data_quality import name_key

MAX_SAME_PLACE_KM = 3.0
# Sources whose coordinates come from surveyed map data are preferred over
# anything else when a group has several positions.
_COORDINATE_SOURCES = ("openstreetmap.org", "wikidata.org", "wikipedia.org")


def _distance_km(a, b):
    lat1, lon1, lat2, lon2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 6371.0 * 2 * math.asin(math.sqrt(min(1.0, h)))


def _coords(record):
    lat, lon = record.get("latitude"), record.get("longitude")
    if lat is None or lon is None or lat != lat or lon != lon:
        return None
    return float(lat), float(lon)


class _UnionFind:
    def __init__(self, size):
        self.parent = list(range(size))

    def find(self, item):
        while self.parent[item] != item:
            self.parent[item] = self.parent[self.parent[item]]
            item = self.parent[item]
        return item

    def union(self, a, b):
        root_a, root_b = self.find(a), self.find(b)
        if root_a != root_b:
            # Keep the lower index (better-ranked record) as the root.
            self.parent[max(root_a, root_b)] = min(root_a, root_b)


def _blank(value):
    return value is None or (isinstance(value, float) and value != value) or value == ""


def merge_place_records(records):
    """Merge records (each carrying ``source_rank`` and ``source_id``).

    Returns merged place dicts with two extra keys: ``images`` (list of
    image dicts, best first) and ``sources`` (list of (source_id, url)).
    """
    ordered = sorted(
        (dict(r) for r in records),
        key=lambda r: (r.get("source_rank", 99), -(r.get("tourism_relevance") or 0)),
    )
    for record in ordered:
        record["name_key"] = name_key(record["place_name"])
        aliases = [a for a in str(record.get("aliases") or "").split("|") if a.strip()]
        record["match_keys"] = list(dict.fromkeys(
            [record["name_key"], *(name_key(alias) for alias in aliases)]
        ))

    uf = _UnionFind(len(ordered))
    by_identifier = {}
    anchors = {}  # (district, name_key) -> [(root index, coords or None)]
    for index, record in enumerate(ordered):
        for identifier in (("wd", record.get("wikidata_id")), ("osm", record.get("osm_id"))):
            if _blank(identifier[1]):
                continue
            if identifier in by_identifier:
                uf.union(by_identifier[identifier], index)
            else:
                by_identifier[identifier] = index

        coords = _coords(record)
        # Wikidata aliases ("Brihadishvara Temple" for "Prahadisvarar
        # Temple") are matched exactly like the primary name.
        for key in record["match_keys"]:
            if not key:
                continue
            slot = anchors.setdefault((record["district"], key), [])
            for position, (anchor_index, anchor_coords) in enumerate(slot):
                if coords is None or anchor_coords is None or _distance_km(coords, anchor_coords) <= MAX_SAME_PLACE_KM:
                    uf.union(anchor_index, index)
                    if anchor_coords is None and coords is not None:
                        slot[position] = (anchor_index, coords)
                    break
            else:
                slot.append((index, coords))

    groups = {}
    for index, record in enumerate(ordered):
        groups.setdefault(uf.find(index), []).append(record)
    groups = _merge_spelling_variants(groups)
    return [_merge_group(group) for _, group in sorted(groups.items())]


FUZZY_NAME_THRESHOLD = 0.88
_TRANSLITERATION_RULES = (
    ("ee", "i"), ("ii", "i"), ("oo", "u"), ("uu", "u"), ("aa", "a"), ("zh", "l"), ("th", "t"), ("dh", "d"),
    ("bh", "b"), ("kh", "k"), ("gh", "g"), ("ph", "p"), ("sh", "s"), ("w", "v"), ("y", "i"),
)


def phonetic_key(key):
    """Collapse common Tamil transliteration differences in a name key."""
    import re
    for source, target in _TRANSLITERATION_RULES:
        key = key.replace(source, target)
    return re.sub(r"(.)\1+", r"\1", key)


def _merge_spelling_variants(groups):
    """Attach a group without coordinates to the same-district group with
    coordinates whose name is a close spelling variant.

    Tamil names are transliterated inconsistently ("Brihadeeswara" /
    "Brihadisvara", "Thiruparankundram" / "Tirupparankundram"), so exact keys
    miss many matches between government sources (no coordinates) and
    OSM/Wikidata (coordinates). Each located group absorbs at most one
    variant, which keeps generic names from collapsing together.
    """
    import difflib

    located_by_district = {}
    for root, group in groups.items():
        if any(_coords(r) for r in group):
            located_by_district.setdefault(group[0]["district"], []).append(root)

    claimed = set()
    for root in sorted(groups):
        group = groups.get(root)
        if not group or any(_coords(r) for r in group):
            continue
        key = phonetic_key(group[0]["name_key"])
        if len(key) < 6:
            continue
        best, best_score = None, FUZZY_NAME_THRESHOLD
        for candidate in located_by_district.get(group[0]["district"], []):
            if candidate in claimed:
                continue
            candidate_keys = {k for r in groups[candidate] for k in r.get("match_keys", [r["name_key"]]) if k}
            score = max(difflib.SequenceMatcher(None, key, phonetic_key(k)).ratio() for k in candidate_keys)
            if score >= best_score:
                best, best_score = candidate, score
        if best is not None:
            claimed.add(best)
            combined = sorted(groups[best] + group, key=lambda r: r.get("source_rank", 99))
            groups[min(best, root)] = combined
            del groups[max(best, root)]
            located_by_district[group[0]["district"]] = [
                min(best, root) if r == best else r for r in located_by_district[group[0]["district"]]
            ]
            claimed.add(min(best, root))
    return groups


def _merge_group(group):
    best = group[0]
    merged = dict(best)

    def first(field):
        return next((r[field] for r in group if not _blank(r.get(field))), None)

    for field in ("city", "address", "subcategory", "wikidata_id", "osm_id", "description"):
        merged[field] = first(field)

    # A specific category from any source beats the generic default.
    merged["category_name"] = next(
        (r["category_name"] for r in group if r.get("category_name") and r["category_name"] != "Cultural"),
        best.get("category_name") or "Cultural",
    )

    with_coords = [r for r in group if _coords(r)]
    if with_coords:
        surveyed = [r for r in with_coords if any(s in str(r.get("source_url") or "") for s in _COORDINATE_SOURCES)]
        coords = _coords((surveyed or with_coords)[0]) or (None, None)
        merged["latitude"], merged["longitude"] = coords

    merged["tourism_relevance"] = max((r.get("tourism_relevance") or 0) for r in group)

    images, seen_images = [], set()
    # Freely licensed Commons images first, then official photographs.
    for record in sorted(group, key=lambda r: 0 if r.get("image_source") == "Wikimedia Commons" else 1):
        url = record.get("image_url")
        if _blank(url) or url in seen_images:
            continue
        seen_images.add(url)
        images.append({
            "image_url": url, "image_source": record.get("image_source"),
            "image_license": record.get("image_license"), "image_author": record.get("image_author"),
            "source_id": record.get("source_id"),
        })
    merged["images"] = images

    sources = []
    for record in group:
        pair = (record.get("source_id"), record.get("source_url") or "")
        if pair not in sources:
            sources.append(pair)
    merged["sources"] = sources
    return merged


# ---------------------------------------------------------------------------
# Spelling-variant duplicates already in the database
# ---------------------------------------------------------------------------
# "MGM Dizzee World" / "MGM Dizee World", "Alamparai Fort" / "Alambarai Fort",
# "Udayagiriswarar koil" / "Udayagiriswararkoil". The rules are strict on
# purpose: neighbouring temples often differ by one syllable of the deity's
# name ("Valeeswarar" / "Malleeswarar" Temple, Mylapore).

SPELLING_DUPLICATE_THRESHOLD = 0.88
SPELLING_DUPLICATE_MAX_KM = 2.0
LARGE_AREA_MAX_KM = 15.0
_LARGE_AREA_TYPES = {"sanctuary", "lake", "hill", "island"}

# Words that only say what kind of place it is -> one canonical type each.
_PLACE_TYPES = {
    "temple": "temple", "temples": "temple", "kovil": "temple", "koil": "temple", "koyil": "temple",
    "kovils": "temple", "thirukoil": "temple", "alayam": "temple",
    "church": "church", "cathedral": "church", "basilica": "church",
    "mosque": "mosque", "masjid": "mosque", "dargah": "dargah", "darga": "dargah",
    "madam": "mutt", "mutt": "mutt", "math": "mutt",
    "fort": "fort", "palace": "palace", "mahal": "palace",
    "cave": "cave", "caves": "cave",
    "falls": "falls", "waterfall": "falls", "waterfalls": "falls", "aruvi": "falls",
    "beach": "beach", "lake": "lake", "dam": "dam", "museum": "museum",
    "mandapa": "mandapam", "mandapam": "mandapam", "memorial": "memorial",
    "park": "park", "garden": "park", "gardens": "park", "sanctuary": "sanctuary",
    "hill": "hill", "hills": "hill", "malai": "hill", "peak": "hill",
    "island": "island", "lighthouse": "lighthouse", "reservoir": "dam",
}
# One deity, many names: "Maruthamalai Murugan Temple" is the "Arulmigu
# Subramaniaswamy Temple, Maruthamalai".
_DEITY_SYNONYMS = (
    (r"^(?:subra[h]?man\w*|murug\w*|karthike\w*|kartikey\w*|shanmuga\w*|kandasw\w*|kandasam\w*|"
     r"d[h]?andayuthapani\w*)$", "murugan"),
)
# Renamed sites, by name key -> current name.
_KNOWN_RENAMES = {
    "indira gandhi national park": "Anamalai Tiger Reserve",
    "indira gandhi wildlife sanctuary": "Anamalai Tiger Reserve",
    "indira gandhi wild life sanctuary": "Anamalai Tiger Reserve",
}
# Multi-word kinds of place, folded into one type word first.
_TYPE_PHRASES = (
    (r"\bwater\s+falls?\b", "waterfalls"),  # "Hogenakkal Water Falls"
    (r"\b(?:national\s+park|wild\s*life\s+sanctuary|wild\s*life\s+reserve|tiger\s+reserve|"
     r"birds?\s+sanctuary)\b", "sanctuary"),
)
# Words that carry no identity at all.
_FILLER_WORDS = {"arulmigu", "sri", "shri", "shree", "sree", "the", "csi", "new", "old", "and", "of", "at", "swamy",
                 "swami", "samy", "thiru", "tiru"}


# Extra type words that still describe the same site.
_SAME_SITE_TYPES = {"park", "memorial", "mandapam", "museum"}
# Voicing differs freely in transliteration (Kamuthi / Kamudi, Nagar / Nakar).
_VOICING = str.maketrans({"g": "k", "b": "p", "d": "t", "j": "s", "z": "s", "c": "s", "h": ""})


def _same_consonants(a, b):
    """Spelling variants differ in vowels, doubling or a dropped letter -
    never in a substituted consonant ("Kachaleeswarar" vs "Kapaleeswarar")."""
    import difflib
    import re
    skeleton = lambda key: re.sub(r"(.)\1+", r"\1", re.sub(r"[aeiouy]", "", key.translate(_VOICING)))  # noqa: E731
    opcodes = difflib.SequenceMatcher(None, skeleton(a), skeleton(b)).get_opcodes()
    changed = [(tag, max(i2 - i1, j2 - j1)) for tag, i1, i2, j1, j2 in opcodes if tag != "equal"]
    return all(tag != "replace" for tag, _ in changed) and sum(size for _, size in changed) <= 2


def _name_parts(place_name, district=None):
    """(identity key, place types, locality key) for duplicate checks."""
    import re
    from services.data_quality import name_key
    head, _, rest = str(place_name or "").partition(",")
    head = _KNOWN_RENAMES.get(name_key(head), head)
    for pattern, replacement in _TYPE_PHRASES:
        head = re.sub(pattern, replacement, head, flags=re.IGNORECASE)
    district_tokens = set(name_key(district).split()) if district else set()
    tokens = name_key(head).split()
    for pattern, replacement in _DEITY_SYNONYMS:
        tokens = [replacement if re.match(pattern, token) else token for token in tokens]
    types = {_PLACE_TYPES[t] for t in tokens if t in _PLACE_TYPES}
    identity = "".join(t for t in tokens
                       if t not in _PLACE_TYPES and t not in _FILLER_WORDS and t not in district_tokens)
    # "Udayagiriswararkoil" carries its type glued to the name (only looked
    # for when no separate type word exists: "Viralimalai Sanctuary").
    for word, kind in _PLACE_TYPES.items():
        if not types and len(word) >= 4 and identity.endswith(word) and identity != word:
            types.add(kind)
            identity = identity[: -len(word)]
            break
    locality = phonetic_key(name_key(rest.split(",")[0])).replace(" ", "") if rest.strip() else ""
    return re.sub(r"(.)\1+", r"\1", phonetic_key(identity)), types, locality


def _village_in_name(bare_identity, village, identity):
    """True when ``bare_identity`` is village + identity written as one name
    ("maruthamalai" + "murugan"), allowing transliteration differences."""
    import difflib
    if len(village) < 4 or not bare_identity:
        return False
    combined = (village + identity).translate(_VOICING)
    return difflib.SequenceMatcher(None, bare_identity.translate(_VOICING), combined).ratio() >= 0.92


def _same_locality(a, b):
    import difflib
    return difflib.SequenceMatcher(None, a, b).ratio() >= 0.85


def place_localities(place):
    """Village keys named by a place and by the entries merged into it."""
    names = [place.get("place_name"), *str(place.get("merged_names") or "").split("|")]
    return {loc for loc in (_name_parts(name, place.get("district"))[2] for name in names if name) if loc}


def is_spelling_duplicate(a, b):
    """True when two place records of one district are the same place spelt differently.

    ``a``/``b`` are dicts with place_name, district, latitude, longitude and
    location_precision ("locality" = village-centre approximation).
    """
    import difflib
    id_a, types_a, _ = _name_parts(a.get("place_name"), a.get("district"))
    id_b, types_b, _ = _name_parts(b.get("place_name"), b.get("district"))
    locs_a, locs_b = place_localities(a), place_localities(b)
    # "Maruthamalai Murugan Temple" names its village inside the name; its
    # twin "Arulmigu Subramaniaswamy Temple, Maruthamalai" after a comma.
    if not locs_a and locs_b and len(id_b) >= 5:
        for loc in locs_b:
            if _village_in_name(id_a, loc, id_b):
                return (types_a == types_b) and _same_consonants(id_a, loc + id_b)
    if not locs_b and locs_a and len(id_a) >= 5:
        for loc in locs_a:
            if _village_in_name(id_b, loc, id_a):
                return (types_a == types_b) and _same_consonants(id_b, loc + id_a)
    if len(id_a) < 5 or len(id_b) < 5 or id_a[0] != id_b[0]:
        return False
    # Same kind of place. A bare name ("Pykara", "Nagore") is usually the
    # town or area, not the waterfall / dam / dargah named after it; an
    # extra type word may only describe the same site ("Dam" / "Dam Park").
    if bool(types_a) != bool(types_b) or not (types_a <= types_b or types_b <= types_a):
        return False
    if (types_a ^ types_b) - _SAME_SITE_TYPES:
        return False  # "... Temple" vs "... Kovil Beach"
    # Compare with voicing evened out: "Alamparai" / "Alambarai", "Kamuthi" / "Kamudi".
    similarity = difflib.SequenceMatcher(None, id_a.translate(_VOICING), id_b.translate(_VOICING)).ratio()
    if similarity < SPELLING_DUPLICATE_THRESHOLD or not _same_consonants(id_a, id_b):
        return False
    coords_a, coords_b = _coords(a), _coords(b)
    if locs_a and locs_b:
        # Both name their village (directly or through entries merged into
        # them earlier): every village must be the same one.
        return all(any(_same_locality(x, y) for y in locs_b) for x in locs_a) and \
            all(any(_same_locality(y, x) for x in locs_a) for y in locs_b)
    if locs_a or locs_b:
        # "Kamakshi Amman Temple" (Kanchipuram) vs "... Temple, Mangadu":
        # only the same place when the two are actually close together.
        return bool(coords_a and coords_b) and _distance_km(coords_a, coords_b) <= 3.0
    exact = [r for r in (a, b) if _coords(r) and r.get("location_precision") != "locality"]
    if len(exact) == 2:
        # Reserves, lakes and hills are large: their mapped centres can sit
        # several km apart (Anamalai Tiger Reserve / Indira Gandhi National Park).
        limit = LARGE_AREA_MAX_KM if types_a & _LARGE_AREA_TYPES else SPELLING_DUPLICATE_MAX_KM
        return _distance_km(_coords(exact[0]), _coords(exact[1])) <= limit
    # Without two surveyed positions the names alone must be near-identical.
    return similarity >= 0.92
