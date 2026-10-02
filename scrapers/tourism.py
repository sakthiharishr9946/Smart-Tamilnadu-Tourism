"""Tourism place collectors - public entry points.

The implementations live in ``scrapers.government`` (Tamil Nadu government
sources) and ``scrapers.opendata`` (OpenStreetMap and Wikidata). This module
keeps the long-standing import paths used by the app, scripts and tests, and
the file import/export helpers.
"""

from pathlib import Path

import pandas as pd

from scrapers.government import (  # noqa: F401 (public re-exports)
    ARCHAEOLOGY_EXCAVATIONS_URL, ARCHAEOLOGY_MONUMENTS_URL, ARCHAEOLOGY_MUSEUMS_URL,
    DISTRICT_GOVERNMENT_DOMAINS, FOREST_ECOTOURISM_URL, HRCE_COMMON_COLLECTION_URL,
    HRCE_TEMPLE_GUIDE_URL, TTDC_DESTINATIONS_URL, WETLANDS_RAMSAR_URL,
    scrape_district_government_tourism, scrape_forest_ecotourism, scrape_hrce_temples,
    scrape_tamilnadu_archaeology, scrape_tamilnadu_wetlands, scrape_ttdc_destinations,
)
from scrapers.opendata import (  # noqa: F401 (public re-exports)
    OVERPASS_FALLBACK_URL, OVERPASS_URL, WIKIDATA_URL,
    scrape_openstreetmap_tourism, scrape_openstreetmap_tourism_by_district, scrape_wikidata_tourism,
)

# MTC's bus tourist-places page is no longer collected: it lists ten
# well-known sites (all covered by TTDC/OSM/Wikidata) and gives no district,
# so six of them were being filed under the wrong district (Chennai).
MTC_TOURIST_PLACES_URL = "https://mtcbus.tn.gov.in/Home/touristplaces"

# Former names, kept so existing callers keep working.
scrape_government_tourism = scrape_forest_ecotourism
scrape_tamilnadutourism_directory = scrape_ttdc_destinations


def load_tourism_data(file_path):
    path = Path(file_path)

    if not path.exists():
        return pd.DataFrame()

    try:
        if path.suffix.lower() == ".csv":
            return pd.read_csv(path)

        if path.suffix.lower() in [".xlsx", ".xls"]:
            return pd.read_excel(path)

        if path.suffix.lower() == ".json":
            return pd.read_json(path)

    except Exception:
        return pd.DataFrame()

    return pd.DataFrame()


def save_tourism_data(df, file_path):
    if df is None or df.empty:
        return False

    path = Path(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    try:
        if path.suffix.lower() == ".csv":
            df.to_csv(path, index=False)
            return True

        if path.suffix.lower() in [".xlsx", ".xls"]:
            df.to_excel(path, index=False)
            return True

        if path.suffix.lower() == ".json":
            df.to_json(path, orient="records", indent=2)
            return True

    except Exception:
        return False

    return False


def collect_tourism_data(file_path):
    return load_tourism_data(file_path)
