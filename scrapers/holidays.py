"""Tamil Nadu public holidays (and the festival holidays derived from them).

Dates come from the ``holidays`` package's India / Tamil Nadu (``TN``)
calendar, which covers state holidays such as Pongal, Thiruvalluvar Day,
Uzhavar Thirunal and Tamil New Year as well as the lunar-calendar festivals
whose dates move every year. The State Government's annual G.O. remains the
legal authority; a CSV exported from it can be loaded with
``load_holiday_data`` to override these dates.
"""

import datetime
import re
from pathlib import Path

import pandas as pd

APPLICABILITY = "Tamil Nadu"

# Public holidays that are civic days rather than festivals.
_CIVIC_HOLIDAYS_RE = re.compile(
    r"republic day|independence day|gandhi|ambedkar|may day|labou?r day|new year's day|bank|"
    r"election|account", re.IGNORECASE)
_CULTURAL_FESTIVALS_RE = re.compile(r"pongal|thiruvalluvar|uzhavar|puthandu|tamil new year|onam", re.IGNORECASE)


def collect_holiday_rows(years=None):
    """Holiday rows for the holidays table: name, date, year, applicability, type."""
    import holidays

    today = datetime.date.today()
    years = list(years or (today.year, today.year + 1))
    calendar = holidays.country_holidays("IN", subdiv="TN", years=years)
    rows = []
    for date, names in sorted(calendar.items()):
        # A single day can carry several holidays ("Ambedkar Jayanti; Puthandu").
        for name in (part.strip() for part in names.split(";")):
            if name:
                rows.append({
                    "holiday_name": name,
                    "date": date.isoformat(),
                    "year": date.year,
                    "applicability": APPLICABILITY,
                    "holiday_type": "Public",
                })
    return rows


def festivals_from_holidays(rows):
    """Statewide festival rows for holiday dates that are festivals."""
    festivals = []
    for row in rows:
        name = row["holiday_name"]
        if _CIVIC_HOLIDAYS_RE.search(name):
            continue
        festivals.append({
            "festival_name": name,
            "district": None,
            "start_date": row["date"],
            "end_date": row["date"],
            "month": int(row["date"][5:7]),
            "festival_type": "Cultural" if _CULTURAL_FESTIVALS_RE.search(name) else "Religious",
            "importance": "HIGH",
            "expected_tourism_impact": "High statewide visitor movement around this public holiday.",
        })
    return festivals


def load_holiday_data(file_path):
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


def save_holiday_data(df, file_path):
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


def collect_holiday_data(file_path=None, years=None):
    """Holidays from ``file_path`` when it has rows, else the TN calendar."""
    if file_path:
        data = load_holiday_data(file_path)
        if not data.empty:
            return data
    return pd.DataFrame(collect_holiday_rows(years))
