import asyncio
import json
from pathlib import Path

import pytest

from app.adapters.carrier_query import general_adapter as general_adapter_module
from app.adapters.carrier_query.fiftyone_tracking import FiftyOneTrackingAircargoError
from app.adapters.carrier_query.general_adapter import GeneralAdapter
from app.adapters.carrier_query.registry import registry
from app.models.enums import CarrierQueryMethod, QueryStatus
from app.parsers.registry import parser_registry

FIXTURE = Path(__file__).parent / "fixtures" / "fiftyone_tracking_aircargo_sample.json"


def _run(coro):
    return asyncio.run(coro)


def _load_sample() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_query_success_returns_normalized_raw_response(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, str] = {}

    def fake_query(awb: str):
        captured["awb"] = awb
        return _load_sample()

    monkeypatch.setattr(general_adapter_module, "query_fiftyone_tracking_aircargo", fake_query)

    result = _run(GeneralAdapter().query("784-83633734"))

    assert captured["awb"] == "78483633734"
    assert result.status == QueryStatus.SUCCESS
    assert result.carrier_code == "UNKNOWN"
    assert result.adapter_code == "general_adapter"
    assert result.query_method == CarrierQueryMethod.PROTOCOL
    assert result.raw_response is not None
    assert result.raw_response["waybill_info"]["carrier_text"] == "China Southern"
    assert result.raw_response["booking_info"][0]["flight_no"] == "CZ307"


def test_query_not_found_returns_failed_with_raw_response(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_query(awb: str):
        raw = _load_sample()
        raw["found"] = False
        raw["orders"] = []
        return raw

    monkeypatch.setattr(general_adapter_module, "query_fiftyone_tracking_aircargo", fake_query)

    result = _run(GeneralAdapter().query("784-83633734"))

    assert result.status == QueryStatus.FAILED
    assert result.error_code == "awb_not_found"
    assert result.raw_response is not None


def test_query_stale_cache_returns_partial_success(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_query(awb: str):
        raw = _load_sample()
        raw["cache"]["stale"] = True
        raw["cache"]["error"] = {"message": "timeout"}
        return raw

    monkeypatch.setattr(general_adapter_module, "query_fiftyone_tracking_aircargo", fake_query)

    result = _run(GeneralAdapter().query("784-83633734"))

    assert result.status == QueryStatus.PARTIAL_SUCCESS
    assert result.error_code == "stale_cache"
    assert result.error_message == "timeout"
    assert result.raw_response is not None


def test_query_maps_http_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_query(awb: str):
        raise FiftyOneTrackingAircargoError("HTTP 503", status=503)

    monkeypatch.setattr(general_adapter_module, "query_fiftyone_tracking_aircargo", fake_query)

    result = _run(GeneralAdapter().query("784-83633734"))

    assert result.status == QueryStatus.FAILED
    assert result.error_code == "http_503"


def test_query_rejects_invalid_waybill_no(monkeypatch: pytest.MonkeyPatch) -> None:
    def must_not_be_called(*args, **kwargs):
        raise AssertionError("query should not be called")

    monkeypatch.setattr(general_adapter_module, "query_fiftyone_tracking_aircargo", must_not_be_called)

    result = _run(GeneralAdapter().query("ABC-XYZ"))

    assert result.status == QueryStatus.FAILED
    assert result.error_code == "invalid_waybill_no"


def test_general_adapter_registered() -> None:
    assert registry.get("general_adapter") is not None
    assert parser_registry.get("general_adapter") is not None
