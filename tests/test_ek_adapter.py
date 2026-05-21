import asyncio
import json
from pathlib import Path

import pytest

from app.adapters.carrier_query import ek_adapter as ek_adapter_module
from app.adapters.carrier_query.ek_adapter import EKAdapter
from app.adapters.carrier_query.emirates_skycargo import EmiratesSkyCargoError, normalize_awb_for_query
from app.adapters.carrier_query.registry import registry
from app.models.enums import CarrierQueryMethod, QueryStatus
from app.parsers.registry import parser_registry

FIXTURE = Path(__file__).parent / "fixtures" / "emirates_skycargo_sample.json"


def _run(coro):
    return asyncio.run(coro)


def _load_sample() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_normalize_awb_for_query_removes_dash_and_spaces() -> None:
    assert normalize_awb_for_query("176-28780780") == "17628780780"
    assert normalize_awb_for_query(" 176 28780780 ") == "17628780780"


def test_query_success_returns_normalized_raw_response(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, str] = {}

    def fake_query(awb: str):
        captured["awb"] = awb
        return _load_sample()

    monkeypatch.setattr(ek_adapter_module, "query_emirates_skycargo", fake_query)

    result = _run(EKAdapter().query("176-28780780"))

    assert captured["awb"] == "17628780780"
    assert result.status == QueryStatus.SUCCESS
    assert result.carrier_code == "EK"
    assert result.adapter_code == "ek_adapter"
    assert result.query_method == CarrierQueryMethod.PROTOCOL
    assert result.raw_response is not None
    assert result.raw_response["waybill_info"]["official_waybill_no"] == "176-28780780"
    assert result.raw_response["booking_info"][0]["flight_no"] == "EK9873"


def test_query_accepts_unformatted_waybill_no(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, str] = {}

    def fake_query(awb: str):
        captured["awb"] = awb
        return _load_sample()

    monkeypatch.setattr(ek_adapter_module, "query_emirates_skycargo", fake_query)

    result = _run(EKAdapter().query("17628780780"))

    assert result.status == QueryStatus.SUCCESS
    assert captured["awb"] == "17628780780"


def test_query_not_found_returns_failed_with_raw_response(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_query(awb: str):
        raw = _load_sample()
        raw["found"] = False
        raw["orders"] = []
        return raw

    monkeypatch.setattr(ek_adapter_module, "query_emirates_skycargo", fake_query)

    result = _run(EKAdapter().query("176-28780780"))

    assert result.status == QueryStatus.FAILED
    assert result.error_code == "awb_not_found"
    assert result.raw_response is not None


def test_query_detail_error_returns_partial_success(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_query(awb: str):
        raw = _load_sample()
        raw["raw"]["detailErrors"] = [{"bookingReferenceNumber": "65080768", "error": "boom"}]
        return raw

    monkeypatch.setattr(ek_adapter_module, "query_emirates_skycargo", fake_query)

    result = _run(EKAdapter().query("176-28780780"))

    assert result.status == QueryStatus.PARTIAL_SUCCESS
    assert result.error_code == "detail_partial_failed"
    assert result.raw_response is not None
    assert len(result.raw_response["booking_info"]) == 2


def test_query_maps_emirates_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_query(awb: str):
        raise EmiratesSkyCargoError("HTTP 503", status=503)

    monkeypatch.setattr(ek_adapter_module, "query_emirates_skycargo", fake_query)

    result = _run(EKAdapter().query("176-28780780"))

    assert result.status == QueryStatus.FAILED
    assert result.error_code == "http_503"


def test_ek_registered() -> None:
    assert registry.get("ek_adapter") is not None
    assert parser_registry.get("ek_adapter") is not None
