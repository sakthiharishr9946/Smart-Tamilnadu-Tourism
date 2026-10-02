"""Collectors for Tamil Nadu government tourism sources.

Each ``scrape_*`` function returns a DataFrame of place records (see
``scrapers.parsing.PLACE_COLUMNS``). Problems that affect only part of a
source are listed in ``frame.attrs["warnings"]``; a source that cannot be
reached at all raises ``SourceUnavailable`` so the refresh report shows it as
failed instead of silently returning nothing.
"""

import io
import json
import logging
import re
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urljoin, urlparse

import pandas as pd
import requests

from config.districts import TN_DISTRICTS
from config.settings import DATA_DIR
from scrapers.http_client import HttpClient, SourceUnavailable, short_error
from scrapers.parsing import (
    classify_category, clean_place_name, html_to_text, is_junk_place_name, make_place,
    records_frame as _frame, soup, truncate,
)
from services.data_quality import resolve_district

logger = logging.getLogger(__name__)

FOREST_ECOTOURISM_URL = "https://www.forests.tn.gov.in/pages/view/Eco-tourism_Sites"
HRCE_TEMPLE_GUIDE_URL = "https://hrce.tn.gov.in/hrcehome/hrce_templeguide.php"
HRCE_COMMON_COLLECTION_URL = "https://hrce.tn.gov.in/hrcehome/commoncollection_centre.php"
ARCHAEOLOGY_MONUMENTS_URL = "https://www.tnarch.gov.in/monuments-subnames"
ARCHAEOLOGY_EXCAVATIONS_URL = "https://www.tnarch.gov.in/archaeology-excavation"
ARCHAEOLOGY_MUSEUMS_URL = "https://www.tnarch.gov.in/site-museums"
WETLANDS_RAMSAR_URL = "https://tnswa.tn.gov.in/ramsar-convention.php"
TTDC_BASE_URL = "https://www.tamilnadutourism.tn.gov.in"
TTDC_DESTINATIONS_URL = TTDC_BASE_URL + "/destinations"
PINCODE_CACHE_PATH = Path(DATA_DIR) / "cache" / "pincode_districts.json"

# Official district administration portals (S3WaaS / NIC platform).
DISTRICT_GOVERNMENT_DOMAINS = {
    "Ariyalur": "ariyalur.nic.in", "Chengalpattu": "chengalpattu.nic.in",
    "Chennai": "chennai.nic.in", "Coimbatore": "coimbatore.nic.in",
    "Cuddalore": "cuddalore.nic.in", "Dharmapuri": "dharmapuri.nic.in",
    "Dindigul": "dindigul.nic.in", "Erode": "erode.nic.in",
    "Kallakurichi": "kallakurichi.nic.in", "Kancheepuram": "kancheepuram.nic.in",
    "Kanyakumari": "kanniyakumari.nic.in", "Karur": "karur.nic.in",
    "Krishnagiri": "krishnagiri.nic.in", "Madurai": "madurai.nic.in",
    "Mayiladuthurai": "mayiladuthurai.nic.in", "Nagapattinam": "nagapattinam.nic.in",
    "Namakkal": "namakkal.nic.in", "Nilgiris": "nilgiris.nic.in",
    "Perambalur": "perambalur.nic.in", "Pudukkottai": "pudukkottai.nic.in",
    "Ramanathapuram": "ramanathapuram.nic.in", "Ranipet": "ranipet.nic.in",
    "Salem": "salem.nic.in", "Sivaganga": "sivaganga.nic.in",
    "Tenkasi": "tenkasi.nic.in", "Thanjavur": "thanjavur.nic.in",
    "Theni": "theni.nic.in", "Thoothukudi": "thoothukudi.nic.in",
    "Tiruchirappalli": "tiruchirappalli.nic.in", "Tirunelveli": "tirunelveli.nic.in",
    "Tirupathur": "tirupathur.nic.in", "Tiruppur": "tiruppur.nic.in",
    "Tiruvallur": "tiruvallur.nic.in", "Tiruvannamalai": "tiruvannamalai.nic.in",
    "Tiruvarur": "tiruvarur.nic.in", "Vellore": "vellore.nic.in",
    "Viluppuram": "viluppuram.nic.in", "Virudhunagar": "virudhunagar.nic.in",
}
_DOMAIN_TO_DISTRICT = {domain: district for district, domain in DISTRICT_GOVERNMENT_DOMAINS.items()}

MONTHS = ("january", "february", "march", "april", "may", "june", "july", "august",
          "september", "october", "november", "december")
_MONTH_RE = re.compile(r"\b(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|"
                       r"sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\b", re.IGNORECASE)
_DATE_WORDS_RE = re.compile(r"\b(?:month|months|of|the|in|and|season)\b|" + _MONTH_RE.pattern, re.IGNORECASE)
_FESTIVAL_WORDS_RE = re.compile(
    r"\b(festival|festivals|thiruvizha|vizha|utsavam|utsav|brahmotsavam|pongal|jallikattu|deepam|navarat?hri|"
    r"car festival|ther|float|feast|kandoori|urs|santhanakoodu|carnival|fair|mela|exhibition|flower show|"
    r"celebration|jayanthi|jayanti|day|puja|pooja|mahotsav|kumbabishekam|aadi|chithirai|thaipusam|"
    r"panguni|vaikasi|masi|karthigai|shivaratri|sivarathri)\b", re.IGNORECASE)
_RELIGIOUS_WORDS_RE = re.compile(
    r"\b(temple|lord|goddess|deity|deities|thiruvizha|brahmotsavam|deepam|car festival|ther|feast|church|"
    r"kandoori|urs|dargah|santhanakoodu|kumbabishekam|thaipusam|shivaratri|sivarathri|navarat?hri|puja|pooja)\b",
    re.IGNORECASE)


def _month_number(text):
    match = _MONTH_RE.search(text or "")
    if not match:
        return None
    prefix = match.group(1)[:3].casefold()
    return next(i for i, month in enumerate(MONTHS, start=1) if month.startswith(prefix))


# ---------------------------------------------------------------------------
# District administration portals (S3WaaS platform, all 38 districts)
# ---------------------------------------------------------------------------

def _s3waas_post_container(page):
    main = page.find("main") or page
    return main.select_one("div[id^=post-]") or main.select_one(".entry-content") or main


def parse_s3waas_tourist_cards(html, page_url):
    """Destination cards on a ``/tourist-places/`` listing page."""
    page = soup(html)
    cards = []
    for link in page.select("ul.touristContainer a.txtHeading, .touristContainer a.txtHeading"):
        item = link.find_parent("li") or link.parent
        image = item.select_one("a.photoImgContainer img") if item else None
        snippet = item.find("p") if item else None
        cards.append({
            "name": link.get("title") or link.get_text(" ", strip=True),
            "url": urljoin(page_url, link.get("href", "")),
            "description": snippet.get_text(" ", strip=True) if snippet else None,
            "image_url": urljoin(page_url, image["src"]) if image and image.get("src") else None,
        })
    next_link = page.select_one("a.next.page-numbers, link[rel=next], .pagination a.next")
    next_url = urljoin(page_url, next_link["href"]) if next_link and next_link.get("href") else None
    category_links = [
        urljoin(page_url, option.get("value"))
        for option in page.select("#tourist_place_category option")
        if option.get("value") and "tourist-place-category" in option.get("value")
    ]
    return cards, next_url, category_links


def parse_s3waas_detail(html):
    """Full description and a full-size image from a ``/tourist-place/<slug>/`` page."""
    page = soup(html)
    container = _s3waas_post_container(page)
    paragraphs = []
    for paragraph in container.find_all("p"):
        text = paragraph.get_text(" ", strip=True)
        if len(text) > 40 and not text.lower().startswith(("by air", "by train", "by road")):
            paragraphs.append(text)
        if sum(len(p) for p in paragraphs) > 500:
            break
    image = None
    for img in container.find_all("img"):
        src = img.get("src") or ""
        if "/uploads/" in src and "bfi_thumb" not in src:
            image = src
            break
    return (" ".join(paragraphs) or None), image


def parse_s3waas_tourism_index(html, page_url):
    """Rows of the ``/tourism/`` index table: (label, absolute url)."""
    page = soup(html)
    rows = []
    for row in _s3waas_post_container(page).select("table tr"):
        cells = row.find_all("td")
        link = row.find("a", href=True)
        if len(cells) >= 2 and link:
            rows.append((cells[0].get_text(" ", strip=True), urljoin(page_url, link["href"])))
    return rows


def parse_heading_destinations(html, page_url, district, category_hint=None):
    """Named attractions on a content page that lists several in headings
    (e.g. Tenkasi "Famous Falls": Main Falls, Five Falls, ...)."""
    container = _s3waas_post_container(soup(html))
    records = []
    for heading in container.find_all(["h2", "h3", "h4", "h5", "strong"]):
        name = clean_place_name(heading.get_text(" ", strip=True))
        if len(name.split()) > 8 or classify_category(name, default=None) is None:
            continue
        description = None
        following = heading.find_next("p")
        if following is not None:
            description = following.get_text(" ", strip=True)
        record = make_place(name, district, page_url, category_hint=category_hint, description=description,
                            tourism_relevance=0.8)
        if record:
            records.append(record)
    return records


def parse_festival_page(html, page_url, district):
    """Festival entries such as "Chithirai Festival (April/May) :"."""
    container = _s3waas_post_container(soup(html))
    festivals, seen = [], set()
    for element in container.find_all(["h2", "h3", "h4", "h5", "strong", "b", "p", "li"]):
        text = " ".join(element.get_text(" ", strip=True).split())
        is_heading = element.name not in ("p", "li")
        if not text or len(text) > 120 or (not is_heading and not text.rstrip().endswith(":")):
            continue
        month = _month_number(text)
        name = re.split(r"\s+[–—-]\s+|\s*\(|:", text, maxsplit=1)[0]
        name = clean_place_name(name)
        if not name or len(name) > 80 or (month is None and not _FESTIVAL_WORDS_RE.search(name)):
            continue
        # "Month of April" and similar date-only headings are not festivals.
        if not _DATE_WORDS_RE.sub("", name).strip(" -/&,"):
            continue
        if is_junk_place_name(name) and not _FESTIVAL_WORDS_RE.search(name):
            continue
        key = name.casefold()
        if key in seen:
            continue
        seen.add(key)
        next_paragraph = element.find_next("p")
        description = next_paragraph.get_text(" ", strip=True) if next_paragraph is not None else None
        if description and description.startswith(text[:30]):
            following = next_paragraph.find_next("p")
            description = following.get_text(" ", strip=True) if following is not None else None
        festivals.append({
            "festival_name": name,
            "district": district,
            "month": month,
            "festival_type": "Religious" if _RELIGIOUS_WORDS_RE.search(f"{name} {description or ''}") else "Cultural",
            "importance": "MEDIUM",
            "description": truncate(description, 400) if description else None,
            "source_url": page_url,
        })
    return festivals


_SKIP_INDEX_LABELS = ("how to reach", "tourist information", "accommodation", "hotel", "lodge", "contact",
                      "travel", "transport", "map", "gallery")


def _crawl_district_portal(client, district, fetch_details=True, max_listing_pages=10):
    domain = DISTRICT_GOVERNMENT_DOMAINS[district]
    base = f"https://{domain}/"
    places, festivals, warnings = [], [], []

    index_html = client.try_get_text(urljoin(base, "tourism/"))
    rows = parse_s3waas_tourism_index(index_html, urljoin(base, "tourism/")) if index_html else []
    listing_urls = [url for label, url in rows if "tourist-place" in url]
    festival_urls = [url for label, url in rows if re.search(r"festiv|event", f"{label} {url}", re.I)]
    content_pages = [
        (label, url) for label, url in rows
        if url not in listing_urls and url not in festival_urls
        and urlparse(url).netloc == domain
        and not any(skip in label.casefold() for skip in _SKIP_INDEX_LABELS)
    ]
    if not listing_urls:
        listing_urls = [urljoin(base, "tourist-places/")]
    if not festival_urls:
        festival_urls = [urljoin(base, "festivals-and-events/"), urljoin(base, "events-festivals/")]

    cards, visited = [], set()
    queue = list(dict.fromkeys(listing_urls))
    while queue and len(visited) < max_listing_pages:
        url = queue.pop(0)
        if url in visited:
            continue
        visited.add(url)
        html = client.try_get_text(url)
        if not html:
            continue
        page_cards, next_url, category_links = parse_s3waas_tourist_cards(html, url)
        cards.extend(page_cards)
        for link in [next_url, *category_links]:
            if link and link not in visited and urlparse(link).netloc == domain:
                queue.append(link)
    if not index_html and not visited.intersection(listing_urls) and not cards:
        raise SourceUnavailable(f"{domain} unreachable")

    seen_urls = set()
    for card in cards:
        if card["url"] in seen_urls:
            continue
        seen_urls.add(card["url"])
        description, image = card["description"], card["image_url"]
        if fetch_details and urlparse(card["url"]).netloc == domain:
            detail_html = client.try_get_text(card["url"])
            if detail_html:
                full_description, full_image = parse_s3waas_detail(detail_html)
                description = full_description or description
                image = full_image or image
        record = make_place(
            card["name"], district, card["url"], description=description,
            image_url=image, image_source=f"{district} District Administration" if image else None,
            tourism_relevance=0.9,
        )
        if record:
            places.append(record)

    for label, url in content_pages:
        html = client.try_get_text(url)
        if html:
            places.extend(parse_heading_destinations(html, url, district, category_hint=label))

    for url in festival_urls:
        html = client.try_get_text(url)
        if html:
            festivals.extend(parse_festival_page(html, url, district))
            break

    if not places:
        warnings.append(f"{district}: no destinations found on {domain}")
    return places, festivals, warnings


def scrape_district_government_tourism(client=None, districts=None, fetch_details=True, max_workers=8):
    """Destinations (and festivals, in ``attrs["festivals"]``) from all 38
    district administration portals."""
    client = client or HttpClient(min_interval=0.4)
    targets = list(districts or TN_DISTRICTS)
    places, festivals, warnings, failed = [], [], [], []

    def crawl(district):
        try:
            return district, _crawl_district_portal(client, district, fetch_details=fetch_details), None
        except Exception as error:  # one district must never stop the others
            return district, None, error

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        for district, result, error in pool.map(crawl, targets):
            if error is not None:
                failed.append(district)
                warnings.append(f"{district}: {short_error(error)}")
                continue
            district_places, district_festivals, district_warnings = result
            places.extend(district_places)
            festivals.extend(district_festivals)
            warnings.extend(district_warnings)
            logger.info("District portal %s: %d places, %d festivals", district, len(district_places), len(district_festivals))

    if len(failed) == len(targets):
        raise SourceUnavailable("No district portal could be reached")
    return _frame(places, warnings, festivals=festivals)


# ---------------------------------------------------------------------------
# Tamil Nadu Tourism (TTDC) official website
# ---------------------------------------------------------------------------

# Listing pages on tamilnadutourism.tn.gov.in and the category they imply.
# ``None`` means "classify from the destination name".
TTDC_CATEGORY_PAGES = {
    "temples": "Temple", "beaches": "Beach", "waterfalls": "Waterfall", "hills": "Hill",
    "forts": "Historical", "palaces": "Historical", "monuments": "Heritage", "museums": "Heritage",
    "world-heritage-sites": "Heritage", "bird-sanctuaries": "Wildlife", "national-parks": "Wildlife",
    "zoos": "Wildlife", "churches": "Cultural", "mosques": "Cultural", "backwaters": "Nature",
    "lakes": "Nature", "parks": "Nature", "places-of-interest": None,
}
_TTDC_NON_DESTINATION_SLUGS = set(TTDC_CATEGORY_PAGES) | {
    "districts", "cities", "where-to-go", "popular-tourist-places", "pilgrim-centres", "trekking-routes",
}


def parse_ttdc_listing(html, page_url):
    """Destination detail URLs on a TTDC category page."""
    page = soup(html)
    urls = []
    for link in page.select(".img-wrap a[href], a.img-wrap[href]"):
        url = urljoin(page_url, link["href"])
        slug = urlparse(url).path.rstrip("/").rsplit("/", 1)[-1]
        if "/destinations/" in url and slug not in _TTDC_NON_DESTINATION_SLUGS and not slug.endswith("-district"):
            urls.append(url)
    return list(dict.fromkeys(urls))


def parse_ttdc_detail(html):
    """(name, district, description, image) from a TTDC destination page.

    Titles follow "Pichavaram Backwaters | Cuddalore | Tamil Nadu Tourism".
    """
    page = soup(html)
    title = page.title.get_text(" ", strip=True) if page.title else ""
    parts = [part.strip() for part in title.split("|")]
    name = parts[0] if parts else None
    district = resolve_district(parts[1]) if len(parts) >= 3 else None
    if not district:
        for heading in page.find_all("h2"):
            match = re.match(r"explore\s+(.+?)\s+district", heading.get_text(" ", strip=True), re.I)
            if match:
                district = resolve_district(match.group(1))
                break

    def meta(prop):
        tag = page.find("meta", attrs={"property": prop}) or page.find("meta", attrs={"name": prop})
        return tag.get("content") if tag else None

    return name, district, meta("og:description") or meta("description"), meta("og:image")


_TTDC_LOCATION_SUFFIX_RE = re.compile(r"^(?P<name>.{4,}?)\s*(?:,|\s[–—-])\s*(?P<place>[A-Z][\w.']*(?:\s[A-Z][\w.']*)?)$")


def split_ttdc_name(name):
    """'Suruli Falls, Theni' -> ('Suruli Falls', 'Theni'); 'Pykara – Ooty' -> ('Pykara', 'Ooty')."""
    match = _TTDC_LOCATION_SUFFIX_RE.match(clean_place_name(name))
    if not match:
        return clean_place_name(name), None
    return match.group("name").strip(), match.group("place").strip()


def choose_ttdc_category(name, listing_categories, listing_sizes):
    """Pick a category for a destination listed on one or more TTDC pages.

    Listing pages also show carousels of destinations from other categories,
    so a destination can appear under "Temples" without being one. The name's
    own signal wins when it agrees with a listing; otherwise the smallest
    (most specific) listing it appears on is used.
    """
    named = classify_category(name, default=None)
    categories = [c for c in listing_categories if c]
    if named and (named in categories or not categories):
        return named
    if categories:
        return min(categories, key=lambda c: listing_sizes.get(c, 0))
    return named or "Cultural"


def scrape_ttdc_destinations(client=None, max_workers=4):
    """Destinations published by the Tamil Nadu Tourism Development Corporation."""
    client = client or HttpClient(min_interval=0.4)
    listings, listing_sizes, pages_read = {}, {}, 0
    warnings = []
    for slug, category in TTDC_CATEGORY_PAGES.items():
        url = f"{TTDC_DESTINATIONS_URL}/{slug}"
        html = client.try_get_text(url)
        if not html:
            warnings.append(f"TTDC listing unavailable: {slug}")
            continue
        pages_read += 1
        urls = parse_ttdc_listing(html, url)
        if category:
            listing_sizes[category] = listing_sizes.get(category, 0) + len(urls)
        for detail_url in urls:
            listings.setdefault(detail_url, []).append(category)
    if not listings:
        raise SourceUnavailable("No TTDC destination listing could be read")
    # A destination featured in the site-wide banner shows up on every
    # listing page; its category must come from its name alone.
    for detail_url, categories in listings.items():
        if pages_read > 2 and len(categories) > pages_read / 2:
            listings[detail_url] = []

    def fetch(item):
        url, categories = item
        html = client.try_get_text(url)
        if not html:
            return None, f"TTDC page unavailable: {url}"
        raw_name, district, description, image = parse_ttdc_detail(html)
        if not district:
            return None, f"TTDC page without a Tamil Nadu district: {url}"
        name, place = split_ttdc_name(raw_name)
        record = make_place(
            name, district, url, city=place if place and place.casefold() != district.casefold() else None,
            category_name=choose_ttdc_category(raw_name, categories, listing_sizes), description=description,
            image_url=image, image_source="Tamil Nadu Tourism" if image else None, tourism_relevance=1.0,
        )
        return record, None

    records = []
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        for record, warning in pool.map(fetch, listings.items()):
            if record:
                records.append(record)
            elif warning:
                warnings.append(warning)
    logger.info("TTDC: %d destinations from %d pages", len(records), len(listings))
    return _frame(records, warnings)


# ---------------------------------------------------------------------------
# Forest Department eco-tourism sites
# ---------------------------------------------------------------------------

def parse_forest_ecotourism(html, page_url=FOREST_ECOTOURISM_URL):
    """Eco-tourism cards. Sections are *forest circles*, not districts, so the
    district is taken from the name's parenthetical, then the linked district
    portal, and only then from the circle name."""
    page = soup(html)
    records = []
    for card in page.select("h5.promo-percent"):
        raw_name = card.get_text(" ", strip=True)
        link = card.find_parent("a")
        href = link.get("href") if link else None
        section = card.find_previous("div", class_="section-title")
        circle = section.get_text(" ", strip=True) if section else None

        name, city, district = raw_name, None, None
        paren = re.search(r"\(([^)]+)\)\s*$", raw_name)
        if paren:
            inner = paren.group(1).strip()
            name = raw_name[:paren.start()].strip()
            district = resolve_district(inner)
            if not district and len(inner.split()) <= 2 and not re.search(r"falls|perennial|sanctuary", inner, re.I):
                city = inner
        if not district and href:
            district = _DOMAIN_TO_DISTRICT.get(urlparse(href).netloc.lower())
        if not district:
            district = resolve_district(circle)
        record = make_place(
            name, district, href or page_url, city=city, subcategory="eco-tourism",
            description=f"Eco-tourism site listed by the Tamil Nadu Forest Department ({circle} circle)." if circle else None,
            tourism_relevance=0.8,
        )
        if record:
            if record["category_name"] == "Cultural":
                record["category_name"] = "Nature"
            records.append(record)
    return records


def scrape_forest_ecotourism(client=None):
    client = client or HttpClient()
    try:
        html = client.get_text(FOREST_ECOTOURISM_URL)
    except requests.RequestException as error:
        raise SourceUnavailable(short_error(error)) from error
    records = parse_forest_ecotourism(html)
    if not records:
        raise SourceUnavailable("Forest Department page layout changed: no eco-tourism cards found")
    # Cards that link to an official TTDC page get their district from it:
    # that is authoritative, whereas the forest circle is only a fallback.
    for record in records:
        if urlparse(record["source_url"] or "").netloc.endswith("tamilnadutourism.tn.gov.in"):
            detail = client.try_get_text(record["source_url"])
            if detail:
                district = parse_ttdc_detail(detail)[1]
                if district:
                    record["district"] = district
    return _frame(records)


# ---------------------------------------------------------------------------
# State Wetlands Authority (Ramsar sites)
# ---------------------------------------------------------------------------

def parse_wetlands(html, page_url=WETLANDS_RAMSAR_URL):
    records = []
    for table in pd.read_html(io.StringIO(html)):
        columns = {str(c).casefold().strip(): c for c in table.columns}
        name_col = next((c for k, c in columns.items() if "wetland" in k and "name" in k), None)
        district_col = next((c for k, c in columns.items() if "district" in k), None)
        if name_col is None or district_col is None:
            continue
        for _, row in table.iterrows():
            name = str(row.get(name_col) or "").strip()
            if not name or name.casefold() == "nan":
                continue
            # Some sites span two districts ("Nagapattinam and Tiruvarur").
            for part in re.split(r"\s+and\s+|,|&", str(row.get(district_col) or "")):
                district = resolve_district(part)
                record = make_place(
                    name, district, page_url, subcategory="ramsar wetland",
                    category_name="Wildlife" if re.search(r"bird|wildlife|sanctuary|reserve", name, re.I) else "Nature",
                    description="Wetland of international importance (Ramsar site) listed by the Tamil Nadu State Wetlands Authority.",
                    tourism_relevance=0.8,
                )
                if record:
                    records.append(record)
    return records


def scrape_tamilnadu_wetlands(client=None):
    client = client or HttpClient()
    try:
        html = client.get_text(WETLANDS_RAMSAR_URL)
    except requests.RequestException as error:
        raise SourceUnavailable(short_error(error)) from error
    records = parse_wetlands(html)
    if not records:
        raise SourceUnavailable("Wetlands page layout changed: no Ramsar table found")
    return _frame(records)


# ---------------------------------------------------------------------------
# HR&CE temples (public Common Collection Centre PDF)
# ---------------------------------------------------------------------------

_HRCE_LINE_RE = re.compile(
    r"^(?P<serial>\d+)(?P<head>\.)?\s+(?P<name>.+?)\s*-\s*(?P<pin>\d{6})\s*\[(?P<tm>TM\d+)\]\s*(?:\((?P<ccc>CCC)\))?\s*$"
)
_HRCE_REGION_RE = re.compile(r"^(?:Joint|Assistant|Deputy)\s+Commissioner,\s*(?P<region>[A-Za-z .'-]+?)(?:\s+[IV]+)?$", re.I)


def parse_hrce_lines(lines):
    """Temple identity lines -> dicts with name, locality, pincode and region.

    Only identity fields are kept (policy): no officer, finance or land data.
    """
    temples, region = [], None
    for raw in lines:
        line = " ".join(str(raw).split())
        region_match = _HRCE_REGION_RE.match(line)
        if region_match:
            region = region_match.group("region").strip()
            continue
        match = _HRCE_LINE_RE.match(line)
        if not match:
            continue
        full_name = match.group("name").strip().rstrip(",")
        parts = [p.strip() for p in full_name.split(",") if p.strip()]
        temples.append({
            "name": full_name,
            "locality": parts[-1] if len(parts) > 1 else None,
            "pincode": match.group("pin"),
            "tm_id": match.group("tm"),
            "is_centre": bool(match.group("ccc")),
            "region": region,
        })
    return temples


class PincodeDistrictResolver:
    """PIN code -> district, persisted to disk because the mapping is stable.

    HR&CE groups temples by administrative *region* (e.g. the Dharmapuri Joint
    Commissioner also covers Krishnagiri), so the temple's own PIN code is the
    reliable way to place it in the right district.
    """

    def __init__(self, client, cache_path=PINCODE_CACHE_PATH):
        self.client = client
        self.cache_path = Path(cache_path)
        self._lock = threading.Lock()
        try:
            self.cache = json.loads(self.cache_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            self.cache = {}

    def save(self):
        with self._lock:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            self.cache_path.write_text(json.dumps(self.cache, indent=0, sort_keys=True), encoding="utf-8")

    def _lookup_india_post(self, pincode):
        response = self.client.get(f"https://api.postalpincode.in/pincode/{pincode}")
        payload = response.json()
        offices = []
        if payload and payload[0]:
            offices = payload[0].get("PostOffice") or []
        for office in offices:
            if str(office.get("State", "")).casefold() == "tamil nadu":
                return resolve_district(office.get("District"))
        return None

    def _lookup_nominatim(self, pincode):
        response = self.client.get(
            "https://nominatim.openstreetmap.org/search",
            params={"postalcode": pincode, "country": "in", "format": "jsonv2", "addressdetails": 1, "limit": 1},
        )
        results = response.json()
        if results and str(results[0].get("address", {}).get("state", "")).casefold() == "tamil nadu":
            return resolve_district(results[0]["address"].get("state_district"))
        return None

    def resolve(self, pincode):
        if pincode in self.cache:
            return self.cache[pincode]
        district, answered = None, False
        for lookup in (self._lookup_india_post, self._lookup_nominatim):
            try:
                district = lookup(pincode)
                answered = True
            except (requests.RequestException, ValueError, KeyError, IndexError, TypeError) as error:
                logger.debug("PIN %s lookup failed: %s", pincode, short_error(error))
                continue
            if district:
                break
        if answered:  # never cache a transient failure
            with self._lock:
                self.cache[pincode] = district
        return district


def scrape_hrce_temples(client=None, resolver=None, max_workers=4):
    """Temples from HR&CE's public Common Collection Centre listing."""
    from pypdf import PdfReader

    client = client or HttpClient(host_intervals={"nominatim.openstreetmap.org": 1.1, "api.postalpincode.in": 0.2})
    try:
        response = client.get(HRCE_COMMON_COLLECTION_URL)
    except requests.RequestException as error:
        raise SourceUnavailable(short_error(error)) from error
    if not response.content.startswith(b"%PDF"):
        raise SourceUnavailable("HR&CE listing is no longer published as a PDF")

    lines = []
    for page in PdfReader(io.BytesIO(response.content)).pages:
        lines.extend((page.extract_text() or "").splitlines())
    temples = parse_hrce_lines(lines)
    if not temples:
        raise SourceUnavailable("HR&CE PDF layout changed: no temple lines found")

    resolver = resolver or PincodeDistrictResolver(client)
    pincodes = sorted({t["pincode"] for t in temples})
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        districts = dict(zip(pincodes, pool.map(resolver.resolve, pincodes)))
    resolver.save()

    records, unresolved = [], 0
    for temple in temples:
        district = districts.get(temple["pincode"]) or resolve_district(temple["region"])
        if not districts.get(temple["pincode"]):
            unresolved += 1
        record = make_place(
            temple["name"], district, HRCE_COMMON_COLLECTION_URL, city=temple["locality"],
            category_name="Temple", subcategory="HR&CE temple",
            description="Temple administered by the Tamil Nadu Hindu Religious and Charitable Endowments Department.",
            tourism_relevance=0.5 if temple["is_centre"] else 0.3,
        )
        if record:
            records.append(record)
    warnings = [f"{unresolved} temples placed by HR&CE region because their PIN code could not be resolved"] if unresolved else []
    return _frame(records, warnings)


# ---------------------------------------------------------------------------
# Department of Archaeology
# ---------------------------------------------------------------------------

def parse_archaeology_tables(html, page_url, category, label):
    records = []
    for table in pd.read_html(io.StringIO(html)):
        columns = {str(c).casefold().strip(): c for c in table.columns}
        district_col = next((c for k, c in columns.items() if "district" in k), None)
        name_col = next((c for k, c in columns.items()
                         if "name of monument" in k or "place of excavation" in k or k in ("name", "monument", "site")), None)
        if district_col is None or name_col is None:
            continue
        location_col = next((c for k, c in columns.items() if "location" in k or "village" in k), None)
        type_col = next((c for k, c in columns.items() if "type of monument" in k or "nature of site" in k), None)
        for _, row in table.iterrows():
            def cell(column):
                value = str(row.get(column) or "").strip() if column is not None else ""
                return "" if value.casefold() in ("nan", "none", "-") else value
            record = make_place(
                cell(name_col), cell(district_col), page_url, city=cell(location_col) or None,
                category_name=category, subcategory=cell(type_col) or None,
                description=f"Publicly listed by the Tamil Nadu Department of Archaeology ({label}).",
                tourism_relevance=0.7,
            )
            if record:
                records.append(record)
    return records


def parse_archaeology_museums(html, page_url=ARCHAEOLOGY_MUSEUMS_URL):
    text = html_to_text(re.sub(r"<script.*?</script>|<style.*?</style>", " ", html, flags=re.I | re.S))
    pattern = re.compile(r"(?P<name>[A-Z][A-Za-z0-9'’&().\- ]{3,100}?(?:Site Museum|Museum|Mahal))"
                         r"[^.]{0,180}?(?P<district>[A-Z][A-Za-z]+(?: [A-Z][A-Za-z]+)?)\s+District")
    records = []
    for match in pattern.finditer(text):
        record = make_place(match.group("name"), match.group("district"), page_url, category_name="Heritage",
                            subcategory="site museum",
                            description="Site museum maintained by the Tamil Nadu Department of Archaeology.",
                            tourism_relevance=0.7)
        if record:
            records.append(record)
    return records


def scrape_tamilnadu_archaeology(client=None):
    client = client or HttpClient(timeout=(15, 45), retries=2)
    records, warnings, reached = [], [], 0
    for url, category, label in ((ARCHAEOLOGY_MONUMENTS_URL, "Heritage", "protected monuments"),
                                 (ARCHAEOLOGY_EXCAVATIONS_URL, "Historical", "excavation sites")):
        html = client.try_get_text(url)
        if not html:
            if not reached:
                # All pages share one host; if the first is down, so is the site.
                raise SourceUnavailable("tnarch.gov.in is unreachable")
            warnings.append(f"Unreachable: {url}")
            continue
        reached += 1
        try:
            records.extend(parse_archaeology_tables(html, url, category, label))
        except ValueError:  # pandas: no tables in page
            warnings.append(f"No tables found on {url}")
    html = client.try_get_text(ARCHAEOLOGY_MUSEUMS_URL)
    if html:
        reached += 1
        records.extend(parse_archaeology_museums(html))
    else:
        warnings.append(f"Unreachable: {ARCHAEOLOGY_MUSEUMS_URL}")
    if not reached:
        raise SourceUnavailable("tnarch.gov.in is unreachable")
    return _frame(records, warnings)
