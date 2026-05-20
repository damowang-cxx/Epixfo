import json
from pathlib import Path

from app.adapters.carrier_query.normalizers.cz import CZNormalizer
from app.models.enums import OfficialEventType
from app.parsers.cz_parser import CZParser

FIXTURE = Path(__file__).parent / "fixtures" / "tang_sample.json"


def _load_tang_sample() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_normalize_translates_top_level_keys() -> None:
    normalized = CZNormalizer().normalize(_load_tang_sample())

    assert set(normalized) >= {"waybill_info", "booking_info", "status_events", "assembly_events"}
    assert normalized["csair"]["awbNo"] == "784-83707805"
    assert normalized["csair"]["milestones"]["received"]["status"] == "done"


def test_normalize_maps_booking_fields() -> None:
    normalized = CZNormalizer().normalize(_load_tang_sample())

    booking = normalized["booking_info"][0]
    assert booking["booking_no"] == "B202605101234"
    assert booking["flight_no"] == "CZ3105"
    assert booking["flight_date"] == "2026-05-12"
    assert booking["weight"] == "1059"
    assert booking["volume"] == "5.20"
    assert booking["departure_airport"] == "广州(CAN)"


def test_normalize_maps_waybill_info_fields() -> None:
    normalized = CZNormalizer().normalize(_load_tang_sample())

    info = normalized["waybill_info"]
    assert info is not None
    assert info["official_waybill_no"] == "784-83707805"
    assert info["carrier_text"] == "CZ/CZ"
    assert info["total_weight"] == "1059"
    assert info["goods_name"] == "GENERAL CARGO"


def test_normalize_handles_missing_optional_sections() -> None:
    normalized = CZNormalizer().normalize({"awbInfo": None})

    assert normalized["waybill_info"] is None
    assert normalized["booking_info"] == []
    assert normalized["status_events"] == []
    assert normalized["assembly_events"] == []


def test_normalized_output_consumable_by_cz_parser() -> None:
    """关键回归：normalizer 的输出能被 CZParser 直接消费、字段对齐。"""
    normalized = CZNormalizer().normalize(_load_tang_sample())
    parsed = CZParser().parse(normalized)

    assert parsed.official_info is not None
    assert parsed.official_info.official_waybill_no == "784-83707805"
    assert parsed.official_info.carrier_text == "CZ/CZ"
    assert str(parsed.official_info.total_weight) == "1059"

    assert len(parsed.flight_segments) == 1
    assert parsed.flight_segments[0].flight_no == "CZ3105"
    assert str(parsed.flight_segments[0].flight_date) == "2026-05-12"

    assert len(parsed.status_events) == 3
    types = [event.normalized_event_type for event in parsed.status_events]
    assert OfficialEventType.ORIGIN_CARGO_RECEIVED in types
    assert OfficialEventType.CARGO_LOADED in types
    assert OfficialEventType.FLIGHT_DEPARTED in types

    assert len(parsed.assembly_events) == 1
    assert parsed.assembly_events[0].uld_no == "AKE12345CZ"
