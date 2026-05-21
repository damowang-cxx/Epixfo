import json
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from app.adapters.carrier_query.normalizers.general import GeneralNormalizer
from app.models.enums import OfficialEventType
from app.parsers.general_parser import GeneralParser

FIXTURE = Path(__file__).parent / "fixtures" / "fiftyone_tracking_aircargo_sample.json"


def _load_sample() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_general_normalizer_maps_cleaned_fields_and_event_types() -> None:
    normalized = GeneralNormalizer().normalize(_load_sample())

    assert normalized["waybill_info"]["official_waybill_no"] == "784-83633734"
    assert normalized["waybill_info"]["carrier_text"] == "China Southern"
    assert normalized["waybill_info"]["route_text"] == "CAN-AMS"
    assert normalized["waybill_info"]["total_pieces"] == "54"
    assert normalized["booking_info"][0]["flight_no"] == "CZ307"
    assert normalized["booking_info"][0]["departure_airport"] == "CAN"
    assert normalized["booking_info"][0]["arrival_airport"] == "AMS"
    assert normalized["booking_info"][0]["flight_date"] == "2026-05-01"
    assert len(normalized["status_events"]) == 6

    event_types = [row["normalized_event_type"] for row in normalized["status_events"]]
    assert event_types == [
        "cargo_received",
        "cargo_loaded",
        "flight_departed",
        "flight_arrived",
        "pickup_notified",
        "picked_up",
    ]


def test_general_parser_outputs_standard_parsed_data() -> None:
    normalized = GeneralNormalizer().normalize(_load_sample())
    parsed = GeneralParser().parse(normalized)

    assert parsed.official_info is not None
    assert parsed.official_info.official_waybill_no == "784-83633734"
    assert parsed.official_info.carrier_text == "China Southern"
    assert parsed.official_info.total_pieces == 54
    assert parsed.official_info.total_weight == Decimal("1040")
    assert parsed.official_info.total_volume == Decimal("6.5")

    assert len(parsed.flight_segments) == 1
    segment = parsed.flight_segments[0]
    assert segment.flight_no == "CZ307"
    assert segment.flight_date == date(2026, 5, 1)
    assert segment.departure_actual_time == datetime(2026, 5, 1, 3, 15, 23)
    assert segment.arrival_actual_time == datetime(2026, 5, 1, 17, 47)

    event_types = [event.normalized_event_type for event in parsed.status_events]
    assert event_types[0] == OfficialEventType.ORIGIN_CARGO_RECEIVED
    assert OfficialEventType.CARGO_LOADED in event_types
    assert OfficialEventType.FLIGHT_DEPARTED in event_types
    assert OfficialEventType.FLIGHT_ARRIVED in event_types
    assert OfficialEventType.PICKUP_NOTIFIED in event_types
    assert OfficialEventType.PICKED_UP in event_types
    assert parsed.status_events[0].airport_code == "CAN"
