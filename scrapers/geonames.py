"""GeoNames gazetteer for Tamil Nadu (free, CC BY 4.0, one download).

https://download.geonames.org/export/dump/IN.zip lists ~40,000 Tamil Nadu
villages and towns, each with coordinates, alternate spellings (including
Tamil script) and its district. It is the village-level backbone for
locating HR&CE temples, which are listed with their village but no
coordinates. The 16 MB file is cached for 30 days.
"""

import io
import logging
import time
import unicodedata
import zipfile
from pathlib import Path

from config.settings import DATA_DIR
from scrapers.http_client import HttpClient
from services.data_quality import resolve_district

logger = logging.getLogger(__name__)

GEONAMES_DUMP_URL = "https://download.geonames.org/export/dump/IN.zip"
GEONAMES_ADMIN2_URL = "https://download.geonames.org/export/dump/admin2Codes.txt"
GEONAMES_DIR = Path(DATA_DIR) / "cache" / "geonames"
GEONAMES_MAX_AGE_SECONDS = 30 * 24 * 3600
TAMIL_NADU_ADMIN1 = "25"

# GeoNames feature code -> settlement rank (lower = more significant).
_SETTLEMENT_RANK = {"PPLC": 0, "PPLA": 0, "PPLA2": 1, "PPLA3": 1, "PPLA4": 2, "PPL": 3, "PPLX": 4,
                    "PPLL": 5, "PPLF": 6}
_WORSHIP_CODES = {"TMPL", "CH", "MSQE", "SHRN", "MSTY", "PGDA"}


def _download(client, url, path, max_age):
    if path.exists() and time.time() - path.stat().st_mtime < max_age:
        return path
    try:
        response = client.get(url)
        GEONAMES_DIR.mkdir(parents=True, exist_ok=True)
        path.write_bytes(response.content)
    except Exception as error:  # noqa: BLE001 - fall back to an older copy
        if not path.exists():
            raise
        logger.warning("GeoNames download failed (%s); using the cached copy", error)
    return path


def _district_names(admin2_path):
    names = {}
    for line in admin2_path.read_text(encoding="utf-8").splitlines():
        code, _, rest = line.partition("\t")
        if code.startswith(f"IN.{TAMIL_NADU_ADMIN1}."):
            name = rest.split("\t")[0].replace(" district", "").replace("Kattabo", "").strip()
            # "Rāmanāthapuram" -> "Ramanathapuram"
            name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
            district = resolve_district(name)
            if district:
                names[code.rsplit(".", 1)[1]] = district
    return names


def parse_geonames(lines, district_names):
    """{district: [gazetteer rows]} from GeoNames dump lines (Tamil Nadu only)."""
    rows = {}
    for line in lines:
        fields = line.rstrip("\n").split("\t")
        if len(fields) < 12 or fields[10] != TAMIL_NADU_ADMIN1:
            continue
        district = district_names.get(fields[11])
        code = fields[7]
        if not district or not (code in _SETTLEMENT_RANK or code in _WORSHIP_CODES):
            continue
        try:
            lat, lon = float(fields[4]), float(fields[5])
        except ValueError:
            continue
        # Plain ASCII name first: it is the one shown in reports.
        names = list(dict.fromkeys(n.strip() for n in [fields[2], fields[1], *fields[3].split(",")] if n.strip()))
        if code in _WORSHIP_CODES:
            row = {"kind": "worship", "lat": lat, "lon": lon, "names": names}
        else:
            row = {"kind": "settlement", "rank": _SETTLEMENT_RANK[code], "lat": lat, "lon": lon, "names": names}
        rows.setdefault(district, []).append(row)
    return rows


def load_geonames_rows(client=None, max_age=GEONAMES_MAX_AGE_SECONDS):
    """{district: rows} for all Tamil Nadu districts (downloads on first use)."""
    client = client or HttpClient(min_interval=1.0, timeout=(15, 300), retries=2)
    dump = _download(client, GEONAMES_DUMP_URL, GEONAMES_DIR / "IN.zip", max_age)
    admin2 = _download(client, GEONAMES_ADMIN2_URL, GEONAMES_DIR / "admin2Codes.txt", max_age)
    district_names = _district_names(admin2)
    with zipfile.ZipFile(dump) as archive, archive.open("IN.txt") as handle:
        return parse_geonames(io.TextIOWrapper(handle, encoding="utf-8"), district_names)
