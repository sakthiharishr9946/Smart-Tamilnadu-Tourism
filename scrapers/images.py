"""Place images: Wikimedia Commons metadata enrichment plus file import/export.

Image candidates are collected by the place scrapers themselves (Wikidata
P18, OSM ``image``/``wikimedia_commons`` tags, government portal photos).
For Commons files this module resolves a display-size thumbnail together
with the licence and author, which Commons' reuse terms require us to show.
"""

import logging
import re
from pathlib import Path
from urllib.parse import unquote

import pandas as pd
import requests

from scrapers.http_client import HttpClient, short_error
from scrapers.parsing import html_to_text

logger = logging.getLogger(__name__)

COMMONS_API_URL = "https://commons.wikimedia.org/w/api.php"
_FILEPATH_RE = re.compile(r"/wiki/Special:FilePath/(?P<name>[^?#]+)", re.IGNORECASE)
_UPLOAD_RE = re.compile(r"upload\.wikimedia\.org/wikipedia/commons/(?:thumb/)?[0-9a-f]/[0-9a-f]{2}/(?P<name>[^/?#]+)")


def commons_file_title(url):
    """'File:Name.jpg' for a Commons FilePath/upload URL, else None."""
    if not url:
        return None
    match = _FILEPATH_RE.search(url) or _UPLOAD_RE.search(url)
    if not match:
        return None
    return "File:" + unquote(match.group("name")).replace("_", " ")


def fetch_commons_metadata(urls, client=None, thumb_width=1024, batch_size=50):
    """{original url: {"image_url", "image_license", "image_author", "description_url"}}.

    Files that no longer exist on Commons are omitted, so callers can drop them.
    """
    client = client or HttpClient(min_interval=0.2)
    titles = {}
    for url in urls:
        title = commons_file_title(url)
        if title:
            titles.setdefault(title, []).append(url)
    results = {}
    title_list = list(titles)
    for start in range(0, len(title_list), batch_size):
        batch = title_list[start:start + batch_size]
        try:
            payload = client.get(COMMONS_API_URL, params={
                "action": "query", "format": "json", "formatversion": 2, "prop": "imageinfo",
                "iiprop": "url|extmetadata", "iiurlwidth": thumb_width,
                "iiextmetadatafilter": "LicenseShortName|Artist|Credit",
                "titles": "|".join(batch),
            }).json()
        except (requests.RequestException, ValueError) as error:
            logger.warning("Commons metadata batch failed: %s", short_error(error))
            continue
        query = payload.get("query", {})
        # Map canonical titles back to the titles we asked for.
        aliases = {item["to"]: item["from"] for item in query.get("normalized", [])}
        for page in query.get("pages", []):
            info = (page.get("imageinfo") or [None])[0]
            if page.get("missing") or not info:
                continue
            requested = aliases.get(page["title"], page["title"])
            meta = info.get("extmetadata") or {}
            value = lambda key: html_to_text((meta.get(key) or {}).get("value")) or None
            entry = {
                "image_url": info.get("thumburl") or info.get("url"),
                "image_license": value("LicenseShortName"),
                "image_author": (value("Artist") or value("Credit") or "")[:200] or None,
                "description_url": info.get("descriptionurl"),
            }
            for original in titles.get(requested, []):
                results[original] = entry
    return results


def load_image_data(file_path):
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


def save_image_data(df, file_path):
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


def collect_image_data(file_path):
    return load_image_data(file_path)
