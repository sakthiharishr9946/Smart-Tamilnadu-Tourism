from scrapers.tourism import (
    HRCE_TEMPLE_GUIDE_URL,
    HRCE_COMMON_COLLECTION_URL,
    ARCHAEOLOGY_MONUMENTS_URL,
    ARCHAEOLOGY_EXCAVATIONS_URL,
    ARCHAEOLOGY_MUSEUMS_URL,
    WETLANDS_RAMSAR_URL,
)


def test_government_source_registry_urls():
    for url in (
        HRCE_TEMPLE_GUIDE_URL,
        HRCE_COMMON_COLLECTION_URL,
        ARCHAEOLOGY_MONUMENTS_URL,
        ARCHAEOLOGY_EXCAVATIONS_URL,
        ARCHAEOLOGY_MUSEUMS_URL,
        WETLANDS_RAMSAR_URL,
    ):
        assert url.startswith("https://")


def test_government_source_domains_are_expected():
    assert "hrce.tn.gov.in" in HRCE_COMMON_COLLECTION_URL
    assert "tnarch.gov.in" in ARCHAEOLOGY_MONUMENTS_URL
    assert "tnswa.tn.gov.in" in WETLANDS_RAMSAR_URL
