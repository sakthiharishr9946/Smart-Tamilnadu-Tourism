from config.districts import TN_DISTRICTS
from scrapers.tourism import DISTRICT_GOVERNMENT_DOMAINS


def test_all_38_districts_have_government_tourism_domain():
    assert len(TN_DISTRICTS) == 38
    assert set(TN_DISTRICTS) == set(DISTRICT_GOVERNMENT_DOMAINS)


def test_southern_district_portals_are_configured():
    for district in ["Tenkasi", "Thoothukudi", "Tirunelveli", "Kanyakumari", "Ramanathapuram", "Sivaganga"]:
        assert district in DISTRICT_GOVERNMENT_DOMAINS
        assert DISTRICT_GOVERNMENT_DOMAINS[district].endswith(".nic.in")
