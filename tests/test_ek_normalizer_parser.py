import json
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from app.adapters.carrier_query.normalizers.ek import EKNormalizer
from app.models.enums import OfficialEventType
from app.parsers.ek_parser import EKParser

FIXTURE = Path(__file__).parent / "fixtures" / "emirates_skycargo_sample.json"


def _load_sample() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_ek_normalizer_maps_waybill_segments_statuses_and_customs() -> None:
    normalized = EKNormalizer().normalize(_load_sample())

    assert normalized["waybill_info"]["official_waybill_no"] == "176-28780780"
    assert normalized["waybill_info"]["route_text"] == "CAN-AMS"
    assert normalized["waybill_info"]["total_pieces"] == 84
    assert normalized["booking_info"][0]["flight_no"] == "EK9873"
    assert normalized["booking_info"][0]["flight_date"] == "2026-05-09"
    assert normalized["booking_info"][0]["departure_planned_time"] == "2026-05-09 15:45:00"
    assert normalized["booking_info"][1]["arrival_actual_time"] == "2026-05-11 13:05:00"

    event_types = [row["normalized_event_type"] for row in normalized["status_events"]]
    assert "cargo_received" in event_types
    assert "cargo_loaded" in event_types
    assert "flight_departed" in event_types
    assert "flight_arrived" in event_types
    assert "pickup_notified" in event_types
    assert "picked_up" in event_types
    assert any(row["status_text"] == "Customs: CUSTOMS CLEARED" for row in normalized["status_events"])


def test_ek_parser_outputs_standard_parsed_data() -> None:
    normalized = EKNormalizer().normalize(_load_sample())
    parsed = EKParser().parse(normalized)

    assert parsed.official_info is not None
    assert parsed.official_info.official_waybill_no == "176-28780780"
    assert parsed.official_info.carrier_text == "EK / Emirates SkyCargo"
    assert parsed.official_info.total_weight == Decimal("1033")
    assert parsed.official_info.total_volume == Decimal("6.0641")

    assert len(parsed.flight_segments) == 2
    first_segment = parsed.flight_segments[0]
    assert first_segment.booking_no == "65080768"
    assert first_segment.departure_airport == "CAN"
    assert first_segment.arrival_airport == "DWC"
    assert first_segment.flight_no == "EK9873"
    assert first_segment.flight_date == date(2026, 5, 9)
    assert first_segment.departure_planned_time == datetime(2026, 5, 9, 15, 45)
    assert first_segment.departure_actual_time == datetime(2026, 5, 9, 15, 34)
    assert first_segment.arrival_planned_time == datetime(2026, 5, 9, 20, 0)
    assert first_segment.arrival_actual_time == datetime(2026, 5, 9, 19, 46)

    event_types = {event.normalized_event_type for event in parsed.status_events}
    assert OfficialEventType.ORIGIN_CARGO_RECEIVED in event_types
    assert OfficialEventType.CARGO_LOADED in event_types
    assert OfficialEventType.FLIGHT_DEPARTED in event_types
    assert OfficialEventType.FLIGHT_ARRIVED in event_types
    assert OfficialEventType.PICKUP_NOTIFIED in event_types
    assert OfficialEventType.PICKED_UP in event_types
    assert any(event.status_text == "Customs: CUSTOMS CLEARED" for event in parsed.status_events)
