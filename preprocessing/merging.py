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
