"""Offline tests for the data collectors.

The HTML/JSON samples below reproduce the structure of the live pages each
parser targets (S3WaaS district portals, TTDC, Forest Department, Wetlands
Authority, HR&CE PDF text, Overpass and Wikidata responses), so a parser
regression is caught without touching the network.
"""

import sqlite3
from pathlib import Path

import pytest

from preprocessing.merging import merge_place_records
from scrapers import government as gov
from scrapers import opendata as od
from scrapers.festivals import combine_festivals
from scrapers.holidays import collect_holiday_rows, festivals_from_holidays
from scrapers.images import commons_file_title
from scrapers.parsing import classify_category, clean_place_name, is_junk_place_name, make_place
from services.data_quality import name_key, resolve_district

# ---------------------------------------------------------------- helpers

S3WAAS_LISTING = """<html><body><main id="SkipContent"><ul class="touristContainer">
<li><a class="photoImgContainer" href="https://madurai.nic.in/tourist-place/palace/"><img src="https://cdn.s3waas.gov.in/x/uploads/bfi_thumb/p.jpg"></a>
 <div class="photoTxtContainer"><a class="txtHeading" href="https://madurai.nic.in/tourist-place/palace/" title="Thirumalai Nayak Palace">Thirumalai Nayak Palace</a>
 <p>About 1.5 Kms from the Meenakshi temple…</p></div></li>
<li><a class="txtHeading" href="https://madurai.nic.in/tourist-place/tpk/" title="Thirupparankundram Temple">Thirupparankundram Temple</a><p>Abode of Murugan</p></li>
</ul><select id="tourist_place_category"><option value="https://madurai.nic.in/tourist-places/">All</option>
<option value="https://madurai.nic.in/tourist-place-category/others/">Others</option></select>
<a class="next page-numbers" href="https://madurai.nic.in/tourist-places/page/2/">Next</a></main></body></html>"""

S3WAAS_INDEX = """<main><div id="post-2805"><table><tr><th>Items</th><th>Link</th></tr>
<tr><td>How to Reach</td><td><a href="https://tenkasi.nic.in/tourism/how-to-reach/">Click Here</a></td></tr>
<tr><td>Tourist Places</td><td><a href="https://tenkasi.nic.in/tourist-places/">Click Here</a></td></tr>
<tr><td>Famous Falls</td><td><a href="https://tenkasi.nic.in/famous-falls/">Click Here</a></td></tr>
</table></div></main>"""

FALLS_PAGE = """<main><div id="post-9"><h2>FAMOUS FALLS</h2><h3>Courtallam</h3>
<h4>Main Falls</h4><p>Main Falls is very near to the bus stand.</p>
<h4>Five Falls</h4><p>Five streams fall side by side.</p><h4>How to Reach</h4><p>By bus.</p></div></main>"""

FESTIVAL_PAGE = """<main><div id="post-1"><h1>Festivals and Events</h1>
<p><strong>Pongal (Harvest Festival) – January :</strong></p><p>Pongal or the Harvest Festival is celebrated…</p>
<p><strong>Chithirai Festival (April/May) :</strong></p><p>Celebrated on the full moon day; Lord Vishnu as Alagar…</p>
<p><strong>Photo Gallery</strong></p></div></main>"""

TTDC_DETAIL = """<html><head><title>Pichavaram Backwaters | Cuddalore | Tamil Nadu Tourism</title>
<meta property="og:description" content="The world's second-largest mangrove forest.">
<meta property="og:image" content="https://www.tamilnadutourism.tn.gov.in/img/p.webp"></head><body></body></html>"""

FOREST_PAGE = """<div class="section-title"><span>Madurai</span></div>
<a href="https://tnwildscapes.com/x/54/kovilar-dam"><h5 class="promo-percent">Kovilar Dam (Virudhunagar)</h5></a>
<a href="https://salem.nic.in/tourist-place/muttal/"><h5 class="promo-percent">Anaivari Muttal</h5></a>
<a href="https://tnwildscapes.com/x/29/pykara"><h5 class="promo-percent">Pykara Waterfalls (Ooty)</h5></a>
<div class="section-title"><span>The Nilgiris</span></div>
<a href="https://tnwildscapes.com/x/44/cairn-hill"><h5 class="promo-percent">Cairn Hill</h5></a>"""

WETLANDS_PAGE = """<table><tr><th>Sl.No</th><th>Name of the Wetland</th><th>District</th></tr>
<tr><td>1</td><td>Point Calimere Wildlife and Bird Sanctuary</td><td>Nagapattinam and Tiruvarur</td></tr>
<tr><td>2</td><td>Longwood Shola Reserved Forest</td><td>The Nilgris</td></tr>
<tr><td>3</td><td>Pichavaram Mangrove</td><td>Cuddalore</td></tr></table>"""


# ---------------------------------------------------------------- parsing

@pytest.mark.parametrize("raw,expected", [
    ("Coimbatore →", "Coimbatore"),
    ("210. Arulmigu Athanur Amman Temple, Chithalandur", "Arulmigu Athanur Amman Temple, Chithalandur"),
    ("KOVALAM BEACH", "Kovalam Beach"),
    ("10 Downing Street", "10 Downing Street"),
    ("Five Falls - Read More", "Five Falls"),
])
def test_clean_place_name(raw, expected):
    assert clean_place_name(raw) == expected


@pytest.mark.parametrize("name", ["Notices", "Media Gallery", "Click Here", "Social Media Links", "Madurai District",
                                  "Coimbatore", "Parks and Gardens", "Famous Falls", "தமிழ்", "https://x.in"])
def test_junk_names_rejected(name):
    assert is_junk_place_name(name)


@pytest.mark.parametrize("name", ["Thirumalai Nayak Palace", "Main Falls", "Vandalur Zoo", "Eco Park"])
def test_real_names_accepted(name):
    assert not is_junk_place_name(name)


@pytest.mark.parametrize("name,category", [
    ("Kapaleeshwarar Temple", "Temple"), ("Five Falls", "Waterfall"), ("Marina Beach", "Beach"),
    ("Vedanthangal Bird Sanctuary", "Wildlife"), ("Gingee Fort", "Historical"), ("Gandhi Memorial Museum", "Heritage"),
    ("Doddabetta Peak", "Hill"), ("Ooty Boat House", "Adventure"), ("Vaigai Dam", "Nature"),
    ("Santhome Basilica", "Cultural"), ("Something Else", "Cultural"),
])
def test_classify_category(name, category):
    assert classify_category(name) == category


@pytest.mark.parametrize("raw,district", [
    ("Thiruvallur", "Tiruvallur"), ("The Nilgris", "Nilgiris"), ("Sivagangai district", "Sivaganga"),
    ("Kanchipuram District", "Kancheepuram"), ("Tirupattur", "Tirupathur"), ("Trichy", "Tiruchirappalli"),
    ("Tirupati", None), ("Puducherry", None), ("Bangalore", None), ("South Arcot", None),
])
def test_resolve_district(raw, district):
    assert resolve_district(raw) == district


def test_make_place_rejects_outside_tamil_nadu_coordinates():
    record = make_place("Some Fort", "Vellore", "u", latitude=19.0, longitude=72.8)
    assert record and record["latitude"] is None and record["longitude"] is None
    assert make_place("Some Fort", "Bangalore", "u") is None
    assert make_place("Anna University", "Chennai", "u") is None


def test_name_key_ignores_honorifics_and_punctuation():
    assert name_key("Sri Meenakshi Amman Temple") == name_key("Meenakshi Amman Temple.")
    assert name_key("X Temple, Hosur") != name_key("X Temple, Arani")


# ---------------------------------------------------------------- district portals

def test_s3waas_listing_cards_pagination_and_categories():
    cards, next_url, categories = gov.parse_s3waas_tourist_cards(S3WAAS_LISTING, "https://madurai.nic.in/tourist-places/")
    assert [c["name"] for c in cards] == ["Thirumalai Nayak Palace", "Thirupparankundram Temple"]
    assert cards[0]["image_url"].endswith("p.jpg")
    assert next_url == "https://madurai.nic.in/tourist-places/page/2/"
    assert categories == ["https://madurai.nic.in/tourist-place-category/others/"]


def test_s3waas_index_and_heading_destinations():
    rows = gov.parse_s3waas_tourism_index(S3WAAS_INDEX, "https://tenkasi.nic.in/tourism/")
    assert ("Famous Falls", "https://tenkasi.nic.in/famous-falls/") in rows
    places = gov.parse_heading_destinations(FALLS_PAGE, "u", "Tenkasi", "Famous Falls")
    assert [p["place_name"] for p in places] == ["Main Falls", "Five Falls"]
    assert places[0]["category_name"] == "Waterfall"
    assert places[0]["description"].startswith("Main Falls is very near")


def test_festival_page_parsing():
    festivals = gov.parse_festival_page(FESTIVAL_PAGE, "u", "Madurai")
    assert [(f["festival_name"], f["month"]) for f in festivals] == [("Pongal", 1), ("Chithirai Festival", 4)]
    assert festivals[0]["description"].startswith("Pongal or the Harvest")
    assert festivals[1]["festival_type"] == "Religious"


# ---------------------------------------------------------------- other government sources

def test_ttdc_detail_takes_district_from_title():
    name, district, description, image = gov.parse_ttdc_detail(TTDC_DETAIL)
    assert (name, district) == ("Pichavaram Backwaters", "Cuddalore")
    assert "mangrove" in description and image.endswith(".webp")


def test_forest_district_resolution_order():
    records = {r["place_name"]: r for r in gov.parse_forest_ecotourism(FOREST_PAGE)}
    assert records["Kovilar Dam"]["district"] == "Virudhunagar"        # from the name's parenthetical
    assert records["Anaivari Muttal"]["district"] == "Salem"           # from the linked district portal
    assert records["Pykara Waterfalls"]["city"] == "Ooty"              # town, not a district
    assert records["Pykara Waterfalls"]["district"] == "Madurai"       # forest circle fallback
    assert records["Cairn Hill"]["district"] == "Nilgiris"


def test_wetlands_split_multi_district_and_fix_typos():
    records = gov.parse_wetlands(WETLANDS_PAGE)
    pairs = {(r["place_name"], r["district"]) for r in records}
    assert ("Point Calimere Wildlife and Bird Sanctuary", "Nagapattinam") in pairs
    assert ("Point Calimere Wildlife and Bird Sanctuary", "Tiruvarur") in pairs
    assert ("Longwood Shola Reserved Forest", "Nilgiris") in pairs


def test_wetlands_scraper_imports_are_complete():
    # Regression: the previous wetlands scraper raised NameError (missing import)
    # inside a bare ``except`` and silently returned nothing.
    import scrapers.government as module
    assert callable(module.scrape_tamilnadu_wetlands)


def test_hrce_line_parsing():
    lines = [
        "Joint Commissioner, Dharmapuri",
        "2. Arulmigu Chanthira Choodeswarar Temple, Hill Station, Chennathur - 635109 [TM004921] (CCC)",
        "1 Arulmigu Nagareswarar Temple, Hosur - 635105 [TM006994]",
        "02-10-2026 00:18:19 Page 2 / 74",
    ]
    temples = gov.parse_hrce_lines(lines)
    assert [t["name"] for t in temples] == [
        "Arulmigu Chanthira Choodeswarar Temple, Hill Station, Chennathur",
        "Arulmigu Nagareswarar Temple, Hosur",
    ]
    assert temples[0]["is_centre"] and not temples[1]["is_centre"]
    assert temples[1]["pincode"] == "635105" and temples[1]["locality"] == "Hosur"
    assert temples[1]["region"] == "Dharmapuri"


def test_pincode_resolver_caches_answers_but_not_failures(tmp_path):
    import requests

    class FakeClient:
        calls = 0

        def get(self, url, **kwargs):
            FakeClient.calls += 1
            if "fail" in url:
                raise requests.ConnectionError("down")

            class Response:
                @staticmethod
                def json():
                    return [{"PostOffice": [{"State": "Tamil Nadu", "District": "Krishnagiri"}]}]
            return Response()

    resolver = gov.PincodeDistrictResolver(FakeClient(), cache_path=tmp_path / "pins.json")
    assert resolver.resolve("635109") == "Krishnagiri"
    resolver.resolve("635109")
    assert FakeClient.calls == 1
    resolver.save()
    assert gov.PincodeDistrictResolver(FakeClient(), cache_path=tmp_path / "pins.json").cache == {"635109": "Krishnagiri"}


# ---------------------------------------------------------------- open data

def test_overpass_parsing_applies_notability_and_generic_name_rules():
    elements = [
        {"type": "node", "id": 1, "lat": 9.92, "lon": 78.12, "tags": {"name": "Gandhi Memorial Museum", "tourism": "museum", "wikidata": "Q1"}},
        {"type": "way", "id": 2, "center": {"lat": 9.91, "lon": 78.11}, "tags": {"name": "Kazimar Big Mosque", "amenity": "place_of_worship", "religion": "muslim", "wikidata": "Q2"}},
        {"type": "node", "id": 3, "lat": 9.9, "lon": 78.1, "tags": {"name": "Village Shrine", "amenity": "place_of_worship"}},
        {"type": "node", "id": 4, "lat": 9.9, "lon": 78.1, "tags": {"name": "Entrance Arch", "historic": "monument"}},
        {"type": "node", "id": 5, "lat": 9.9, "lon": 78.1, "tags": {"name": "Some Hotel", "tourism": "hotel"}},
        {"type": "node", "id": 6, "lat": 9.9, "lon": 78.1, "tags": {"name": "Station Road", "wikidata": "Q6", "highway": "primary"}},
        {"type": "node", "id": 7, "lat": 10.2, "lon": 77.4, "tags": {"name": "Silver Cascade", "natural": "waterfall",
                                                                  "wikimedia_commons": "File:Silver cascade.jpg"}},
    ]
    records = {r["place_name"]: r for r in od.parse_overpass_elements(elements, "Madurai")}
    assert set(records) == {"Gandhi Memorial Museum", "Kazimar Big Mosque", "Silver Cascade"}
    assert records["Kazimar Big Mosque"]["category_name"] == "Cultural"
    assert records["Kazimar Big Mosque"]["latitude"] == 9.91
    assert records["Silver Cascade"]["image_url"].endswith("Special:FilePath/Silver_cascade.jpg")
    assert records["Gandhi Memorial Museum"]["osm_id"] == "node/1"


def test_wikidata_rows_filtered_by_type():
    def row(qid, label, types, lon=78.1, lat=9.9, image=None):
        data = {"place": {"value": f"http://www.wikidata.org/entity/{qid}"}, "placeLabel": {"value": label},
                "coord": {"value": f"Point({lon} {lat})"}, "types": {"value": types}}
        if image:
            data["img"] = {"value": image}
        return data

    rows = [
        row("Q1", "Kallazhagar Temple", "Hindu temple", image="http://commons.wikimedia.org/wiki/Special:FilePath/K.jpg"),
        row("Q2", "HDFC Bank Madurai", "HDFC Bank branch"),
        row("Q3", "Uthapuram", "village in India"),
        row("Q4", "Q4", "Hindu temple"),
        row("Q5", "Vandiyur Lake", "lake"),
    ]
    records = od.parse_wikidata_rows(rows, "Madurai")
    assert [r["place_name"] for r in records] == ["Kallazhagar Temple", "Vandiyur Lake"]
    assert records[0]["image_url"].startswith("https://commons.wikimedia.org/")
    assert records[0]["wikidata_id"] == "Q1"


def test_wikidata_multi_district_item_kept_in_nearest_district():
    def rec(qid, district, lat, lon):
        return {"wikidata_id": qid, "district": district, "latitude": lat, "longitude": lon}
    records = [rec("Q1", "Madurai", 9.92, 78.12), rec("Q2", "Madurai", 9.90, 78.10),
               rec("Q3", "Dindigul", 10.23, 77.49), rec("Q4", "Dindigul", 10.36, 77.98),
               rec("LAKE", "Madurai", 10.23, 77.48), rec("LAKE", "Dindigul", 10.23, 77.48)]
    resolved = od._resolve_multi_district_items(records)
    assert [r["district"] for r in resolved if r["wikidata_id"] == "LAKE"] == ["Dindigul"]


def test_wikidata_multi_district_resolution_tolerates_missing_coordinates():
    # Regression: items whose coordinates fall outside Tamil Nadu have them
    # nulled by make_place; comparing None with floats crashed the source.
    records = [
        {"wikidata_id": "Q1", "district": "Madurai", "latitude": None, "longitude": None},
        {"wikidata_id": "Q2", "district": "Madurai", "latitude": 9.9, "longitude": 78.1},
        {"wikidata_id": "X", "district": "Madurai", "latitude": None, "longitude": None},
        {"wikidata_id": "X", "district": "Theni", "latitude": None, "longitude": None},
    ]
    resolved = od._resolve_multi_district_items(records)
    assert sum(1 for r in resolved if r["wikidata_id"] == "X") == 1


# ---------------------------------------------------------------- merging

def _record(name, district, rank, **extra):
    base = {"place_name": name, "district": district, "category_name": "Cultural", "latitude": None,
            "longitude": None, "source_rank": rank, "source_id": rank, "source_url": f"src{rank}",
            "tourism_relevance": 0.5}
    base.update(extra)
    return base


def test_merge_combines_sources_and_prefers_best_fields():
    records = [
        _record("Gandhi Memorial Museum", "Madurai", 1, description="Official description",
                category_name="Heritage", image_url="https://gov/img.jpg", image_source="District"),
        _record("Gandhi Memorial Museum", "Madurai", 5, latitude=9.93, longitude=78.13, wikidata_id="Q1",
                source_url="https://www.wikidata.org/wiki/Q1",
                image_url="https://commons.wikimedia.org/wiki/Special:FilePath/G.jpg", image_source="Wikimedia Commons"),
        _record("Gandhi Museum", "Madurai", 6, latitude=9.9301, longitude=78.1301, wikidata_id="Q1",
                osm_id="way/9", source_url="https://www.openstreetmap.org/way/9"),
    ]
    merged = merge_place_records(records)
    assert len(merged) == 1
    place = merged[0]
    assert place["place_name"] == "Gandhi Memorial Museum"
    assert place["description"] == "Official description"
    assert place["category_name"] == "Heritage"
    assert (place["latitude"], place["longitude"]) == (9.93, 78.13)
    assert place["osm_id"] == "way/9"
    assert place["images"][0]["image_source"] == "Wikimedia Commons"
    assert len(place["sources"]) == 3


def test_merge_joins_transliteration_variants_only_once():
    records = [
        _record("Brihadeeswara Temple", "Thanjavur", 0, description="TTDC text"),
        _record("Brihadisvara Temple", "Thanjavur", 5, latitude=10.7828, longitude=79.1318, wikidata_id="Q1"),
        _record("Brihadeswara Temple", "Thanjavur", 1),           # second variant: must not also attach
        _record("Kottai Mariamman Temple", "Salem", 0),
        _record("Mariamman Temple", "Salem", 6, latitude=11.6, longitude=78.1),
    ]
    merged = {p["place_name"]: p for p in merge_place_records(records)}
    assert merged["Brihadeeswara Temple"]["latitude"] == 10.7828
    assert merged["Brihadeeswara Temple"]["description"] == "TTDC text"
    assert "Brihadisvara Temple" not in merged
    assert merged["Kottai Mariamman Temple"]["latitude"] is None    # different temple, not merged


def test_merge_keeps_same_named_places_far_apart():
    records = [
        _record("Murugan Temple", "Salem", 6, latitude=11.60, longitude=78.10),
        _record("Murugan Temple", "Salem", 6, latitude=11.90, longitude=78.40),
        _record("Murugan Temple", "Salem", 1),
    ]
    assert len(merge_place_records(records)) == 2


# ---------------------------------------------------------------- holidays, festivals, images

def test_tamil_nadu_holidays_and_festivals():
    rows = collect_holiday_rows([2026])
    names = {row["holiday_name"] for row in rows}
    assert {"Pongal", "Uzhavar Thirunal", "Republic Day"} <= names
    festivals = {f["festival_name"]: f for f in festivals_from_holidays(rows)}
    assert "Republic Day" not in festivals
    assert festivals["Pongal"]["festival_type"] == "Cultural" and festivals["Pongal"]["month"] == 1
    combined = combine_festivals([{"festival_name": "Chithirai Festival", "district": "Madurai", "month": 4}], rows)
    assert any(f["district"] == "Madurai" for f in combined)


def test_commons_file_title():
    assert commons_file_title("https://commons.wikimedia.org/wiki/Special:FilePath/Silver%20cascade.jpg") == "File:Silver cascade.jpg"
    assert commons_file_title("https://upload.wikimedia.org/wikipedia/commons/f/f4/Meenakshi_Tower.jpg") == "File:Meenakshi Tower.jpg"
    assert commons_file_title("https://cdn.s3waas.gov.in/x.jpg") is None


# ---------------------------------------------------------------- database writes

@pytest.fixture()
def temp_db(tmp_path):
    from database.migrations import apply_migrations
    connection = sqlite3.connect(tmp_path / "test.db")
    connection.row_factory = sqlite3.Row
    schema = (Path(__file__).resolve().parent.parent / "database" / "schema.sql").read_text(encoding="utf-8")
    connection.executescript(schema)
    apply_migrations(connection)
    yield tmp_path / "test.db"
    connection.close()


def _ingestor(path):
    from database.ingest import Ingestor
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    return Ingestor(connection)


def test_ingest_is_idempotent_and_keeps_known_fields(temp_db):
    place = {"place_name": "Vaigai Dam", "district": "Theni", "category_name": "Nature", "latitude": 10.05,
             "longitude": 77.59, "description": "A dam", "wikidata_id": "Q7", "source_id": None,
             "images": [{"image_url": "https://img/1.jpg", "image_source": "Wikimedia Commons"}],
             "sources": []}
    with _ingestor(temp_db) as ingestor:
        source_id = ingestor.source_id("Test source", "https://x", "open data")
        place["source_id"] = source_id
        place["sources"] = [(source_id, "https://x/1")]
        first_id, inserted = ingestor.upsert_place(place)
        assert inserted
    # Second run without coordinates/description must not erase them.
    with _ingestor(temp_db) as ingestor:
        second_id, inserted = ingestor.upsert_place({**place, "latitude": None, "longitude": None, "description": None})
        assert second_id == first_id and not inserted
    connection = sqlite3.connect(temp_db)
    row = connection.execute("SELECT latitude, description, name_key FROM places").fetchone()
    assert row == (10.05, "A dam", "vaigai dam")
    assert connection.execute("SELECT COUNT(*), SUM(is_primary) FROM images").fetchone() == (1, 1)
    assert connection.execute("SELECT COUNT(*) FROM place_sources").fetchone() == (1,)


def test_ingest_rolls_back_on_error(temp_db):
    with pytest.raises(RuntimeError):
        with _ingestor(temp_db) as ingestor:
            ingestor.upsert_place({"place_name": "Marina Beach", "district": "Chennai", "category_name": "Beach"})
            raise RuntimeError("boom")
    assert sqlite3.connect(temp_db).execute("SELECT COUNT(*) FROM places").fetchone() == (0,)


def test_festivals_replaced_per_source(temp_db):
    with _ingestor(temp_db) as ingestor:
        source_id = ingestor.source_id("Portals", "https://x", "government")
        ingestor.replace_festivals([{"festival_name": "A"}, {"festival_name": "B"}], source_id)
        ingestor.replace_festivals([{"festival_name": "A"}], source_id)
        ingestor.upsert_holidays([{"holiday_name": "Pongal", "date": "2026-01-14", "year": 2026}] * 2, source_id)
    connection = sqlite3.connect(temp_db)
    assert connection.execute("SELECT COUNT(*) FROM festivals").fetchone() == (1,)
    assert connection.execute("SELECT COUNT(*) FROM holidays").fetchone() == (1,)


def test_cli_source_options_match_scraper_signatures():
    # Regression: --osm-budget passed time_budget to a wrapper that did not accept it.
    import inspect
    from services.data_updates import SOURCES
    scrapers_by_key = {source.key: source.scrape for source in SOURCES}
    inspect.signature(scrapers_by_key["osm"]).bind(time_budget=600)


def test_merge_uses_wikidata_aliases():
    records = [
        _record("Brihadeeswara Temple", "Thanjavur", 0, description="TTDC text"),
        _record("Prahadisvarar Temple", "Thanjavur", 5, latitude=10.783, longitude=79.1325, wikidata_id="Q916943",
                aliases="Big Temple at Thanjavur|Brihadishvara Temple|Peruvudaiyar Kovil"),
        _record("Peruvudaiyar Kovil", "Thanjavur", 1),
    ]
    merged = merge_place_records(records)
    assert len(merged) == 1
    assert merged[0]["place_name"] == "Brihadeeswara Temple"
    assert merged[0]["latitude"] == 10.783
