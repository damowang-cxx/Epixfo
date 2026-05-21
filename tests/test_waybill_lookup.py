import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.adapters.carrier_query.base import CarrierQueryResult
from app.models.enums import CarrierQueryMethod, OfficialEventType, QueryStatus
from app.services import lookup_service as lookup_service_module
from app.services.lookup_service import WaybillLookupService

FIXTURE = Path(__file__).parent / "fixtures" / "tang_sample.json"
EK_FIXTURE = Path(__file__).parent / "fixtures" / "emirates_skycargo_sample.json"
GENERAL_FIXTURE = Path(__file__).parent / "fixtures" / "fiftyone_tracking_aircargo_sample.json"


def _run(coro):
    return asyncio.run(coro)


def _load_tang_sample() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _load_ek_sample() -> dict:
    return json.loads(EK_FIXTURE.read_text(encoding="utf-8"))


def _load_general_sample() -> dict:
    return json.loads(GENERAL_FIXTURE.read_text(encoding="utf-8"))


def _make_service(monkeypatch: pytest.MonkeyPatch, mapping):
    """构造一个 WaybillLookupService，注入桩 CarrierRepository。"""
    service = WaybillLookupService.__new__(WaybillLookupService)
    service.db = None
    service.carriers = SimpleNamespace(get_mapping_by_prefix=lambda prefix: mapping)
    return service


class _StubAdapter:
    def __init__(self, result_or_exc):
        self._result_or_exc = result_or_exc

    async def query(self, waybill_no: str):
        if isinstance(self._result_or_exc, Exception):
            raise self._result_or_exc
        return self._result_or_exc


def test_lookup_success_returns_parsed_data(monkeypatch: pytest.MonkeyPatch) -> None:
    """成功路径：adapter 返回 raw_response → parser 解析 → 拿到结构化数据。"""
    from app.adapters.carrier_query.normalizers.cz import CZNormalizer

    normalized_raw = CZNormalizer().normalize(_load_tang_sample())
    mapping = SimpleNamespace(
        adapter_code="cz_adapter",
        carrier_code="CZ",
        query_method=CarrierQueryMethod.HYBRID,
    )
    adapter = _StubAdapter(
        CarrierQueryResult(
            status=QueryStatus.SUCCESS,
            carrier_code="CZ",
            adapter_code="cz_adapter",
            query_method=CarrierQueryMethod.HYBRID,
            raw_response=normalized_raw,
        )
    )

    monkeypatch.setattr(lookup_service_module.registry, "get", lambda code: adapter)
    service = _make_service(monkeypatch, mapping)

    response = _run(service.lookup("784-83707805"))

    assert response.status == QueryStatus.SUCCESS
    assert response.waybill_no == "784-83707805"
    assert response.carrier_code == "CZ"
    assert response.adapter_code == "cz_adapter"
    assert response.error_code is None
    assert response.official_info is not None
    assert response.official_info.official_waybill_no == "784-83707805"
    assert len(response.flight_segments) == 1
    assert len(response.status_events) == 3
    assert response.assembly_events[0].uld_no == "AKE12345CZ"
    types = [event.normalized_event_type for event in response.status_events]
    assert OfficialEventType.ORIGIN_CARGO_RECEIVED in types
    assert OfficialEventType.FLIGHT_DEPARTED in types


def test_lookup_partial_success_keeps_booking_segments(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.adapters.carrier_query.normalizers.cz import CZNormalizer

    raw = _load_tang_sample()
    raw["awbInfo"] = None
    raw["errorInfo"] = "运单信息不存在"
    normalized_raw = CZNormalizer().normalize(raw)
    mapping = SimpleNamespace(
        adapter_code="cz_adapter",
        carrier_code="CZ",
        query_method=CarrierQueryMethod.HYBRID,
    )
    adapter = _StubAdapter(
        CarrierQueryResult(
            status=QueryStatus.PARTIAL_SUCCESS,
            carrier_code="CZ",
            adapter_code="cz_adapter",
            query_method=CarrierQueryMethod.HYBRID,
            raw_response=normalized_raw,
            error_code="awb_info_not_found",
            error_message="运单信息不存在",
        )
    )

    monkeypatch.setattr(lookup_service_module.registry, "get", lambda code: adapter)
    service = _make_service(monkeypatch, mapping)

    response = _run(service.lookup("784-83707805"))

    assert response.status == QueryStatus.PARTIAL_SUCCESS
    assert response.error_code == "awb_info_not_found"
    assert response.error_message == "运单信息不存在"
    assert response.official_info is None
    assert len(response.flight_segments) == 1


def test_lookup_invalid_waybill_no_short_circuits(monkeypatch: pytest.MonkeyPatch) -> None:
    """运单号格式错误时不应触达 carrier_repository。"""

    def must_not_be_called(prefix):
        raise AssertionError("get_mapping_by_prefix should not be called")

    service = WaybillLookupService.__new__(WaybillLookupService)
    service.db = None
    service.carriers = SimpleNamespace(get_mapping_by_prefix=must_not_be_called)

    response = _run(service.lookup("ABC-XYZ"))

    assert response.status == QueryStatus.FAILED
    assert response.error_code == "invalid_waybill_no"


def test_lookup_unmapped_prefix_falls_back_to_general_adapter(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.adapters.carrier_query.normalizers.general import GeneralNormalizer

    normalized_raw = GeneralNormalizer().normalize(_load_general_sample())
    adapter = _StubAdapter(
        CarrierQueryResult(
            status=QueryStatus.SUCCESS,
            carrier_code="UNKNOWN",
            adapter_code="general_adapter",
            query_method=CarrierQueryMethod.PROTOCOL,
            raw_response=normalized_raw,
        )
    )
    monkeypatch.setattr(lookup_service_module.registry, "get", lambda code: adapter if code == "general_adapter" else None)
    service = _make_service(monkeypatch, mapping=None)

    response = _run(service.lookup("999-12345678"))

    assert response.status == QueryStatus.SUCCESS
    assert response.carrier_code == "UNKNOWN"
    assert response.adapter_code == "general_adapter"
    assert response.official_info is not None
    assert response.official_info.carrier_text == "China Southern"


def test_lookup_adapter_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    mapping = SimpleNamespace(adapter_code="unknown_adapter", carrier_code="UN")
    monkeypatch.setattr(lookup_service_module.registry, "get", lambda code: None)
    service = _make_service(monkeypatch, mapping)

    response = _run(service.lookup("784-83707805"))

    assert response.status == QueryStatus.FAILED
    assert response.error_code == "adapter_not_found"


def test_lookup_unknown_adapter_falls_back_to_general_adapter(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.adapters.carrier_query.normalizers.general import GeneralNormalizer

    normalized_raw = GeneralNormalizer().normalize(_load_general_sample())
    mapping = SimpleNamespace(adapter_code="missing_adapter", carrier_code="ZZ")
    adapter = _StubAdapter(
        CarrierQueryResult(
            status=QueryStatus.SUCCESS,
            carrier_code="UNKNOWN",
            adapter_code="general_adapter",
            query_method=CarrierQueryMethod.PROTOCOL,
            raw_response=normalized_raw,
        )
    )
    monkeypatch.setattr(lookup_service_module.registry, "get", lambda code: adapter if code == "general_adapter" else None)
    service = _make_service(monkeypatch, mapping)

    response = _run(service.lookup("784-83707805"))

    assert response.status == QueryStatus.SUCCESS
    assert response.carrier_code == "ZZ"
    assert response.adapter_code == "general_adapter"


def test_lookup_passes_through_adapter_failed_result(monkeypatch: pytest.MonkeyPatch) -> None:
    """adapter 内部已经把 AwbNotFound / CaptchaFailed 等映射成 CarrierQueryResult(FAILED)；
    lookup 服务原样透传。"""
    mapping = SimpleNamespace(adapter_code="cz_adapter", carrier_code="CZ")
    adapter = _StubAdapter(
        CarrierQueryResult(
            status=QueryStatus.FAILED,
            carrier_code="CZ",
            adapter_code="cz_adapter",
            query_method=CarrierQueryMethod.HYBRID,
            error_code="awb_not_found",
            error_message="运单不存在",
        )
    )

    monkeypatch.setattr(lookup_service_module.registry, "get", lambda code: adapter)
    service = _make_service(monkeypatch, mapping)

    response = _run(service.lookup("784-83707805"))

    assert response.status == QueryStatus.FAILED
    assert response.error_code == "awb_not_found"
    assert response.error_message == "运单不存在"
    assert response.carrier_code == "CZ"
    assert response.adapter_code == "cz_adapter"
    assert response.official_info is None
    assert response.flight_segments == []


def test_lookup_normalizes_waybill_no_to_dashed(monkeypatch: pytest.MonkeyPatch) -> None:
    """输入 11 位数字应被规范化为 `784-83707805`。"""
    mapping = SimpleNamespace(adapter_code="cz_adapter", carrier_code="CZ")
    captured: dict[str, str] = {}

    class _CapturingAdapter:
        async def query(self, waybill_no: str):
            captured["waybill_no"] = waybill_no
            return CarrierQueryResult(
                status=QueryStatus.FAILED,
                carrier_code="CZ",
                adapter_code="cz_adapter",
                query_method=CarrierQueryMethod.HYBRID,
                error_code="awb_not_found",
                error_message="stub",
            )

    monkeypatch.setattr(lookup_service_module.registry, "get", lambda code: _CapturingAdapter())
    service = _make_service(monkeypatch, mapping)

    response = _run(service.lookup("78483707805"))

    assert response.waybill_no == "784-83707805"
    assert captured["waybill_no"] == "784-83707805"


def test_lookup_ek_success_returns_parsed_data(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.adapters.carrier_query.normalizers.ek import EKNormalizer

    normalized_raw = EKNormalizer().normalize(_load_ek_sample())
    mapping = SimpleNamespace(
        adapter_code="ek_adapter",
        carrier_code="EK",
        query_method=CarrierQueryMethod.PROTOCOL,
    )
    adapter = _StubAdapter(
        CarrierQueryResult(
            status=QueryStatus.SUCCESS,
            carrier_code="EK",
            adapter_code="ek_adapter",
            query_method=CarrierQueryMethod.PROTOCOL,
            raw_response=normalized_raw,
        )
    )

    monkeypatch.setattr(lookup_service_module.registry, "get", lambda code: adapter)
    service = _make_service(monkeypatch, mapping)

    response = _run(service.lookup("17628780780"))

    assert response.status == QueryStatus.SUCCESS
    assert response.waybill_no == "176-28780780"
    assert response.carrier_code == "EK"
    assert response.official_info is not None
    assert response.official_info.official_waybill_no == "176-28780780"
    assert len(response.flight_segments) == 2
    assert response.flight_segments[0].flight_no == "EK9873"
    assert response.flight_segments[0].departure_actual_time is not None
    assert any(event.normalized_event_type == OfficialEventType.PICKUP_NOTIFIED for event in response.status_events)
