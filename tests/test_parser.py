from request_parser import parse_request

KEYS = {"task_type", "items", "pickup_location", "dropoff_location",
        "delivery_required", "deadline", "confidence", "missing"}


def test_output_has_every_field():
    assert set(parse_request("I need help with something")) == KEYS


def test_happy_path_shopping():
    r = parse_request("Abeg buy two crates of eggs and one bag of rice for me from Mile 3 before 4pm")
    assert r["task_type"] == "shopping"
    assert r["items"] == [{"name": "eggs", "quantity": 2, "unit": "crates"},
                          {"name": "rice", "quantity": 1, "unit": "bag"}]
    assert r["pickup_location"] == "Mile 3"
    assert r["deadline"] == "before 4pm"
    assert r["delivery_required"] is True
    assert r["missing"] == []
    assert r["confidence"] == 1.0


def test_delivery_with_both_places():
    r = parse_request("Pick up a parcel at Rumuola and drop it at Garrison before 5pm")
    assert r["task_type"] == "delivery"
    assert r["pickup_location"] == "Rumuola"
    assert r["dropoff_location"] == "Garrison"
    assert r["missing"] == []


def test_vague_request_reports_what_is_missing():
    r = parse_request("I need help with something")
    assert r["task_type"] == "other"
    assert set(r["missing"]) == {"task_type", "deadline"}
    assert r["confidence"] == 0.5


def test_failure_path_empty_text_does_not_crash():
    r = parse_request("")
    assert r["task_type"] == "other"
    assert "task_type" in r["missing"]


def test_generic_place_is_flagged_missing():
    r = parse_request("Someone to go the market for me and buy 10 crates of eggs")
    assert r["pickup_location"] is None
    assert set(r["missing"]) == {"pickup_location", "deadline"}
