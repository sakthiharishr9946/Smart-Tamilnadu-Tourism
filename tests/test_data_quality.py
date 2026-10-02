from services.data_quality import filter_tourism_records


def test_filters_educational_and_non_tn_records():
    records = [
        {"place_name": "A College", "district": "Chennai", "category_name": "Cultural"},
        {"place_name": "Gateway Attraction", "district": "Chennai", "category_name": "Cultural"},
        {"place_name": "Other State Museum", "district": "Ahilya Nagar", "category_name": "Heritage"},
    ]
    result = filter_tourism_records(records)
    assert [x["place_name"] for x in result] == ["Gateway Attraction"]
