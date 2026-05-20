import asyncio
import json
from pathlib import Path

import pytest
import requests

from app.adapters.carrier_query import cz_adapter as cz_adapter_module
from app.adapters.carrier_query.cz_adapter import CZAdapter
from app.adapters.carrier_query.csair import AwbAmbiguous, AwbNotFound, CaptchaFailed
from app.models.enums import CarrierQueryMethod, QueryStatus

FIXTURE = Path(__file__).parent / "fixtures" / "tang_sample.json"


def _run(coro):
    return asyncio.run(coro)


def _load_tang_sample() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_query_success_returns_normalized_raw_response(monkeypatch: pytest.MonkeyPatch) -> None:
    sample = _load_tang_sample()

    def fake_query_awb(prefix: str, no: str, debug_dir=None):
        assert prefix == "784"
        assert no == "83707805"
        return sample

    monkeypatch.setattr(cz_adapter_module, "query_awb", fake_query_awb)

    result = _run(CZAdapter().query("784-83707805"))

    assert result.status == QueryStatus.SUCCESS
    assert result.carrier_code == "CZ"
    assert result.adapter_code == "cz_adapter"
    assert result.query_method == CarrierQueryMethod.HYBRID
    assert result.error_code is None
    assert result.raw_response is not None
    assert result.raw_response["waybill_info"]["official_waybill_no"] == "784-83707805"
    assert len(result.raw_response["booking_info"]) == 1
    assert len(result.raw_response["status_events"]) == 3


def test_query_accepts_unformatted_waybill_no(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, str] = {}

    def fake_query_awb(prefix: str, no: str, debug_dir=None):
        captured["prefix"] = prefix
        captured["no"] = no
        return _load_tang_sample()

    monkeypatch.setattr(cz_adapter_module, "query_awb", fake_query_awb)

    result = _run(CZAdapter().query("78483707805"))

    assert result.status == QueryStatus.SUCCESS
    assert captured == {"prefix": "784", "no": "83707805"}


def test_query_rejects_invalid_waybill_no(monkeypatch: pytest.MonkeyPatch) -> None:
    def must_not_be_called(*args, **kwargs):
        raise AssertionError("query_awb should not be called for invalid waybill_no")

    monkeypatch.setattr(cz_adapter_module, "query_awb", must_not_be_called)

    result = _run(CZAdapter().query("ABC-XYZ"))

    assert result.status == QueryStatus.FAILED
    assert result.error_code == "invalid_waybill_no"


def test_query_maps_awb_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_query_awb(prefix: str, no: str, debug_dir=None):
        raise AwbNotFound("运单不存在")

    monkeypatch.setattr(cz_adapter_module, "query_awb", fake_query_awb)

    result = _run(CZAdapter().query("784-83707805"))

    assert result.status == QueryStatus.FAILED
    assert result.error_code == "awb_not_found"
    assert "运单不存在" in (result.error_message or "")


def test_query_maps_awb_ambiguous(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_query_awb(prefix: str, no: str, debug_dir=None):
        raise AwbAmbiguous("国内/国际同单号")

    monkeypatch.setattr(cz_adapter_module, "query_awb", fake_query_awb)

    result = _run(CZAdapter().query("784-83707805"))

    assert result.status == QueryStatus.FAILED
    assert result.error_code == "awb_ambiguous"


def test_query_maps_captcha_failed(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_query_awb(prefix: str, no: str, debug_dir=None):
        raise CaptchaFailed("3 次重试均失败")

    monkeypatch.setattr(cz_adapter_module, "query_awb", fake_query_awb)

    result = _run(CZAdapter().query("784-83707805"))

    assert result.status == QueryStatus.FAILED
    assert result.error_code == "captcha_failed"


def test_query_maps_network_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_query_awb(prefix: str, no: str, debug_dir=None):
        raise requests.ConnectionError("connection refused")

    monkeypatch.setattr(cz_adapter_module, "query_awb", fake_query_awb)

    result = _run(CZAdapter().query("784-83707805"))

    assert result.status == QueryStatus.FAILED
    assert result.error_code == "network_error"


def test_query_maps_unknown_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_query_awb(prefix: str, no: str, debug_dir=None):
        raise RuntimeError("something else")

    monkeypatch.setattr(cz_adapter_module, "query_awb", fake_query_awb)

    result = _run(CZAdapter().query("784-83707805"))

    assert result.status == QueryStatus.FAILED
    assert result.error_code == "unknown_error"
    assert "RuntimeError" in (result.error_message or "")
