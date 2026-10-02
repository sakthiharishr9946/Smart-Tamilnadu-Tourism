"""Free English Wikipedia summaries for destinations.

Article titles come from identifiers the dataset already has - OSM
``wikipedia=en:Title`` tags and Wikidata ``enwiki`` sitelinks - so no
searching or guessing by name is involved. Summaries are fetched 20 per
request from the MediaWiki API (no key, CC BY-SA text).
"""

import difflib
import logging

import requests

from scrapers.http_client import HttpClient, short_error
from services.data_quality import name_key

logger = logging.getLogger(__name__)

WIKIPEDIA_API_URL = "https://en.wikipedia.org/w/api.php"
WIKIDATA_API_URL = "https://www.wikidata.org/w/api.php"
WIKIPEDIA_ARTICLE_URL = "https://en.wikipedia.org/wiki/"

# An article about a different, larger thing (the town a temple stands in)
# is rejected unless its name resembles the place or its location is close.
MIN_TITLE_SIMILARITY = 0.6
MAX_ARTICLE_DISTANCE_KM = 2.0


def _client(client):
    return client or HttpClient(min_interval=0.3, timeout=(10, 60), retries=2)


def osm_wikipedia_title(tags):
    """'Title' for an OSM ``wikipedia`` tag in English ("en:Title"), else None."""
    value = str((tags or {}).get("wikipedia") or "")
    language, _, title = value.partition(":")
    return title.strip() if language.strip() == "en" and title.strip() else None


def wikidata_enwiki_titles(qids, client=None, batch_size=50):
    """{QID: enwiki title} for the items that have an English article."""
    client = _client(client)
    qids = sorted({q for q in qids if q})
    titles = {}
    for start in range(0, len(qids), batch_size):
        batch = qids[start:start + batch_size]
        try:
            payload = client.get(WIKIDATA_API_URL, params={
                "action": "wbgetentities", "format": "json", "props": "sitelinks",
                "sitefilter": "enwiki", "ids": "|".join(batch),
            }).json()
        except (requests.RequestException, ValueError) as error:
            logger.warning("Wikidata sitelinks batch failed: %s", short_error(error))
            continue
        for qid, entity in (payload.get("entities") or {}).items():
            title = ((entity.get("sitelinks") or {}).get("enwiki") or {}).get("title")
            if title:
                titles[qid] = title
    return titles


def fetch_summaries(titles, client=None, batch_size=20):
    """{requested title: {"title", "extract", "image_file", "latitude", "longitude", "url"}}.

    Disambiguation pages and missing articles are omitted. Redirects are
    followed and reported under the title that was asked for.
    """
    client = _client(client)
    titles = sorted({t for t in titles if t})
    summaries = {}
    for start in range(0, len(titles), batch_size):
        batch = titles[start:start + batch_size]
        try:
            payload = client.get(WIKIPEDIA_API_URL, params={
                "action": "query", "format": "json", "formatversion": 2, "redirects": 1,
                "prop": "extracts|pageimages|coordinates|pageprops", "exintro": 1, "explaintext": 1,
                "exsentences": 4, "exlimit": "max", "piprop": "name", "ppprop": "disambiguation",
                "titles": "|".join(batch),
            }).json()
        except (requests.RequestException, ValueError) as error:
            logger.warning("Wikipedia batch failed: %s", short_error(error))
            continue
        query = payload.get("query") or {}
        # requested -> normalised -> redirect target
        renamed = {}
        for item in (query.get("normalized") or []) + (query.get("redirects") or []):
            renamed[item["from"]] = item["to"]

        def final_title(title):
            seen = set()
            while title in renamed and title not in seen:
                seen.add(title)
                title = renamed[title]
            return title

        pages = {page.get("title"): page for page in query.get("pages") or []}
        for requested in batch:
            page = pages.get(final_title(requested))
            if not page or page.get("missing") or "disambiguation" in (page.get("pageprops") or {}):
                continue
            extract = " ".join(str(page.get("extract") or "").split())
            if "may refer to" in extract[:200]:
                continue
            coordinates = (page.get("coordinates") or [{}])[0]
            summaries[requested] = {
                "title": page["title"],
                "extract": extract,
                "image_file": page.get("pageimage"),
                "latitude": coordinates.get("lat"),
                "longitude": coordinates.get("lon"),
                "url": WIKIPEDIA_ARTICLE_URL + page["title"].replace(" ", "_"),
            }
    return summaries


def article_matches_place(summary, place, distance_km=None):
    """True when the article is about this place, not e.g. the town it is in."""
    if distance_km is not None and distance_km <= MAX_ARTICLE_DISTANCE_KM:
        return True
    article = name_key(summary["title"].split("(")[0])
    name = name_key(str(place.get("place_name") or "").split(",")[0])
    if not article or not name:
        return False
    if article in name or name in article:
        return True
    return difflib.SequenceMatcher(None, article, name).ratio() >= MIN_TITLE_SIMILARITY
