from config.districts import TN_DISTRICTS
from database.queries import get_districts


def test_authoritative_tamil_nadu_district_count():
    assert len(TN_DISTRICTS) == 38
    assert "Kanyakumari" in TN_DISTRICTS
    assert "Nilgiris" in TN_DISTRICTS


def test_database_district_list_contains_all_38():
    districts = [row["district"] for row in get_districts()]
    assert districts == TN_DISTRICTS
