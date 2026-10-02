# Smart Tamilnadu Tourism – Data Collection Policy

## Scope
The collector is designed for public tourism discovery across all 38 Tamil Nadu districts.

## Sources (in order of authority)
When sources disagree about a destination's name, description or category, the earlier source wins. Coordinates always come from OpenStreetMap/Wikidata when available, because they are surveyed positions.

| Key | Source | What it provides |
|---|---|---|
| `ttdc` | Tamil Nadu Tourism (tamilnadutourism.tn.gov.in) | Official destinations by category; district from the page title; description and photo |
| `district_portals` | 38 district administration portals (`<district>.nic.in`) | Tourist places, attractions listed on themed pages (falls, dams), district festivals |
| `forest` | Forest Department eco-tourism sites | Eco-tourism destinations |
| `wetlands` | State Wetlands Authority | Ramsar wetland sites |
| `archaeology` | Department of Archaeology (tnarch.gov.in) | Protected monuments, excavation sites, site museums |
| `wikidata` | Wikidata (CC0) | Coordinates, identifiers, Commons images for notable sites |
| `osm` | OpenStreetMap via Overpass (ODbL) | Coordinates for tourism features inside each district boundary |
| `hrce` | HR&CE public Common Collection Centre listing | Temple identity (name, locality); district resolved from the temple's PIN code |

Enrichment steps (run after a refresh, all free and key-less):

| Script | Source | What it provides |
|---|---|---|
| `scripts/enrich_wikipedia.py` | English Wikipedia (CC BY-SA) + Wikimedia Commons | Descriptions for places with a missing/one-line description, photos with licence and author. Only articles linked from the place's own OSM `wikipedia` tag or Wikidata item, and only when the title matches or the article lies within 2 km |
| `scripts/locate_places.py` | GeoNames (CC BY 4.0, `IN.zip`) + cached OSM villages/places of worship | Coordinates for places without them: the place itself when found (exact), otherwise the centre of its village/town (`location_precision = 'locality'`, labelled "approximate" in the app) |
| `scripts/enrich_coordinates.py` | Nominatim (ODbL) | One-by-one geocoding of what is still missing; slow (1 request/second) |

Ratings and reviews come from travellers using the app ("Rate this place" on each destination page); no free service publishes ratings for these places.

Holidays come from the `holidays` package's Tamil Nadu calendar; festival holidays (Pongal, Deepavali, ...) also feed the festivals table.

Sources that are no longer collected:
* **tamilnadutourism.com**: a private site, replaced by the official TTDC website. Its menu links were being stored as places ("Coimbatore →").
* **MTC tourist places**: ten well-known sites with no district information, all already covered by TTDC/OSM/Wikidata.

## Stored fields
Only tourism-relevant fields are retained: place name, district, city/town when publicly available, category, short factual description, coordinates when available, images with source/licence/author, and source URL/provenance (`place_sources` table: every source that listed a place).

## Explicit exclusions
The collector does not intentionally ingest personal contact details, officer details, land/property records, donation/financial records, legal proceedings, authentication information, API keys, or other non-tourism administrative data.

## HR&CE note
The HR&CE website contains an interactive/captcha-protected temple search and a public disclaimer about completeness/accuracy. HR&CE is therefore treated as a supplementary government source. The project extracts only public temple identity information and does not treat the HR&CE dataset as a guarantee of completeness. The listing groups temples by HR&CE administrative region (one region can span several districts), so each temple's district is resolved from its PIN code; lookups are cached in `data/cache/pincode_districts.json`.

## Politeness and reliability
* One identifying User-Agent; per-host request spacing; retries with exponential backoff that honour `Retry-After`.
* Overpass: at most two concurrent queries; each district's response is cached for 7 days in `data/cache/osm/`.
* Wikidata: at most three concurrent queries.
* Nominatim: at most one request per second (PIN codes the India Post lookup could not answer, and `enrich_coordinates.py`).
* GeoNames: one 16 MB download, cached for 30 days in `data/cache/geonames/`. OSM village/temple lists for `locate_places.py --osm-download` are cached for 30 days in `data/cache/osm/gazetteer/`.
* Wikipedia/Wikidata APIs: batched (20-50 titles per request), about three requests per second.
* TLS certificates are always verified. Some government sites serve incomplete certificate chains; these are verified against the operating-system trust store (`truststore`) instead of being skipped.

## Deduplication
Records describing the same destination are merged when they share a Wikidata item, an OSM element, or the same normalised name in the same district. Same-named places more than 3 km apart stay separate.

Several districts were split between 1990 and 2020 (Chengalpattu, Tenkasi, Ranipet, Tirupathur, Kallakurichi, Mayiladuthurai, ...) and sources still file places under the old district. A place with the same name in a parent/split district (`DISTRICT_SPLITS` in `services/data_quality.py`) is treated as the same place when the two are within 15 km or either has no coordinates; every refresh also merges such duplicates already in the database. Source provenance is retained so multiple sources can enrich the same destination without creating duplicates.

## Running a refresh
```
python -m scripts.refresh_data                 # all sources
python -m scripts.refresh_data --reset         # rebuild places from scratch
python -m scripts.refresh_data --sources wikidata osm
python -m scripts.refresh_data --skip hrce --json report.json

python scripts/enrich_wikipedia.py             # descriptions + photos (add --dry-run to preview)
python scripts/locate_places.py                # village/temple coordinates (add --dry-run to preview)
```
The report lists every source's status (`ok`, `partial`, `failed`), row count, duration and warnings. A failing source never stops the others, and all database writes happen in one transaction.

## Fresh rebuild
Use the reset option before a full collection so the database is rebuilt from the current multi-source pipeline instead of mixing old incomplete records with new records. A normal refresh also removes scraping artefacts left by older collector versions.
