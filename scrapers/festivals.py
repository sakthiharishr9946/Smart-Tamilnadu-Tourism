"""Festival data.

Two sources feed the festivals table:

* district festivals ("Chithirai Festival (April/May)") published on the 38
  district administration portals - collected during the district crawl by
  ``scrapers.government.parse_festival_page``;
* statewide festival holidays with exact dates - ``scrapers.holidays``.
"""

import pandas as pd
from pathlib import Path

from scrapers.holidays import festivals_from_holidays

FESTIVAL_COLUMNS = [
    "festival_name", "district", "start_date", "end_date", "month", "festival_type",
    "importance", "expected_tourism_impact", "description", "source_url",
]


def combine_festivals(district_festivals, holiday_rows=()):
    """District + statewide festivals, de-duplicated by (name, district)."""
    combined, seen = [], set()
    for festival in [*festivals_from_holidays(holiday_rows), *(district_festivals or [])]:
        key = (festival["festival_name"].casefold(), festival.get("district") or "",
               festival.get("start_date") or "")
        if key in seen:
            continue
        seen.add(key)
        combined.append({column: festival.get(column) for column in FESTIVAL_COLUMNS})
    return combined


def load_festival_data(file_path):
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


def save_festival_data(df, file_path):
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


def collect_festival_data(file_path):
    return load_festival_data(file_path)