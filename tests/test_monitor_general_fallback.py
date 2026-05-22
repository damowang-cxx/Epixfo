import asyncio
from types import SimpleNamespace

import pytest

from app.adapters.carrier_query.base import CarrierQueryResult
from app.models.enums import CarrierQueryMethod, QueryStatus, WaybillLifecycleStatus
from app.parsers.base import ParsedCarrierData, ParsedOfficialInfo
from app.services import monitor_service as monitor_service_module
from app.services.monitor_service import MonitorService


def _run(coro):
    return asyncio.run(coro)


class _FakeDb:
    def __init__(self) -> None:
        self.added = []

    def add(self, item) -> None:
        self.added.append(item)

    def flush(self) -> None:
        pass

    def commit(self) -> None:
        pass

    def refresh(self, item) -> None:
        pass


class _StubAdapter:
    def __init__(self, result: CarrierQueryResult):
        self.adapter_code = result.adapter_code
        self.carrier_code = result.carrier_code
        self.query_method = result.query_method
        self.result = result
        self.calls: list[str] = []

    async def query(self, waybill_no: str):
        self.calls.append(waybill_no)
        return self.result


def _failed_result(adapter_code: str, carrier_code: str = "UNKNOWN") -> CarrierQueryResult:
    return CarrierQueryResult(
        status=QueryStatus.FAILED,
        carrier_code=carrier_code,
        adapter_code=adapter_code,
        query_method=CarrierQueryMethod.PROTOCOL,
        error_code="awb_not_found",
        error_message="not found",
    )


def _success_result(adapter_code: str, carrier_code: str = "CZ") -> CarrierQueryResult:
    return CarrierQueryResult(
        status=QueryStatus.SUCCESS,
        carrier_code=carrier_code,
        adapter_code=adapter_code,
        query_method=CarrierQueryMethod.PROTOCOL,
        raw_response={"ok": True},
    )


def _make_service(mapping, fallback_enabled: bool = True):
    service = MonitorService.__new__(MonitorService)
    service.db = _FakeDb()
    service.carriers = SimpleNamespace(get_mapping_by_prefix=lambda prefix: mapping)
    service.auto_settings = SimpleNamespace(
        get_model=lambda: SimpleNamespace(
            fallback_enabled=fallback_enabled,
            fallback_adapter_code="general_adapter",
            query_interval_hours=2,
            scan_limit=50,
        )
    )
    service.alerts = SimpleNamespace(
        handle_query_failure=lambda waybill: None,
        handle_query_success=lambda waybill: None,
        check_after_parse=lambda waybill: None,
    )
    service.lifecycle = SimpleNamespace(update_waybill_lifecycle=lambda waybill: None)
    service.waybills = SimpleNamespace(
        replace_official_info=lambda waybill_id, info: None,
        replace_segments=lambda waybill_id, segments: None,
        add_status_events=lambda events: None,
        add_assembly_events=lambda events: None,
    )
    return service


def _patch_parser(monkeypatch: pytest.MonkeyPatch) -> None:
    parser = SimpleNamespace(parse=lambda raw: ParsedCarrierData(official_info=ParsedOfficialInfo(official_waybill_no="x")))
    monkeypatch.setattr(monitor_service_module.parser_registry, "get", lambda code: parser)


def test_monitor_unknown_waybill_uses_general_adapter(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = _StubAdapter(_failed_result("general_adapter"))
    monkeypatch.setattr(monitor_service_module.registry, "get", lambda code: adapter if code == "general_adapter" else None)
    service = _make_service(mapping=None)
    waybill = SimpleNamespace(
        id=1,
        carrier_code="UNKNOWN",
        carrier_prefix="999",
        waybill_no="999-12345678",
        plan=None,
        lifecycle_status=WaybillLifecycleStatus.MONITORING,
    )

    snapshot = _run(service.trigger_query(waybill))

    assert snapshot.adapter_code == "general_adapter"
    assert snapshot.carrier_code == "UNKNOWN"
    assert snapshot.query_status == QueryStatus.FAILED
    assert snapshot.error_code == "awb_not_found"


def test_monitor_missing_specific_adapter_falls_back_and_preserves_carrier(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = _StubAdapter(_failed_result("general_adapter"))
    monkeypatch.setattr(monitor_service_module.registry, "get", lambda code: adapter if code == "general_adapter" else None)
    mapping = SimpleNamespace(adapter_code="missing_adapter", carrier_code="ZZ")
    service = _make_service(mapping=mapping)
    waybill = SimpleNamespace(
        id=2,
        carrier_code="ZZ",
        carrier_prefix="784",
        waybill_no="784-83707805",
        plan=None,
        lifecycle_status=WaybillLifecycleStatus.MONITORING,
    )

    snapshot = _run(service.trigger_query(waybill))

    assert snapshot.adapter_code == "general_adapter"
    assert snapshot.carrier_code == "ZZ"
    assert snapshot.query_status == QueryStatus.FAILED


def test_monitor_specific_adapter_success_does_not_call_general(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_parser(monkeypatch)
    specific = _StubAdapter(_success_result("cz_adapter", "CZ"))
    general = _StubAdapter(_success_result("general_adapter", "UNKNOWN"))
    monkeypatch.setattr(
        monitor_service_module.registry,
        "get",
        lambda code: {"cz_adapter": specific, "general_adapter": general}.get(code),
    )
    mapping = SimpleNamespace(adapter_code="cz_adapter", carrier_code="CZ")
    service = _make_service(mapping=mapping)
    waybill = SimpleNamespace(
        id=3,
        carrier_code="CZ",
        carrier_prefix="784",
        waybill_no="784-83707805",
        plan=None,
        lifecycle_status=WaybillLifecycleStatus.MONITORING,
    )

    snapshot = _run(service.trigger_query(waybill))

    assert snapshot.adapter_code == "cz_adapter"
    assert snapshot.query_status == QueryStatus.SUCCESS
    assert specific.calls == ["784-83707805"]
    assert general.calls == []


def test_monitor_specific_adapter_failure_uses_general_when_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_parser(monkeypatch)
    specific = _StubAdapter(_failed_result("cz_adapter", "CZ"))
    general = _StubAdapter(_success_result("general_adapter", "UNKNOWN"))
    monkeypatch.setattr(
        monitor_service_module.registry,
        "get",
        lambda code: {"cz_adapter": specific, "general_adapter": general}.get(code),
    )
    mapping = SimpleNamespace(adapter_code="cz_adapter", carrier_code="CZ")
    service = _make_service(mapping=mapping, fallback_enabled=True)
    waybill = SimpleNamespace(
        id=4,
        carrier_code="CZ",
        carrier_prefix="784",
        waybill_no="784-83707805",
        plan=None,
        lifecycle_status=WaybillLifecycleStatus.MONITORING,
    )

    snapshot = _run(service.trigger_query(waybill))

    assert snapshot.adapter_code == "general_adapter"
    assert snapshot.carrier_code == "CZ"
    assert snapshot.query_status == QueryStatus.SUCCESS
    assert specific.calls == ["784-83707805"]
    assert general.calls == ["784-83707805"]


def test_monitor_specific_adapter_failure_stops_when_fallback_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    specific = _StubAdapter(_failed_result("cz_adapter", "CZ"))
    general = _StubAdapter(_success_result("general_adapter", "UNKNOWN"))
    monkeypatch.setattr(
        monitor_service_module.registry,
        "get",
        lambda code: {"cz_adapter": specific, "general_adapter": general}.get(code),
    )
    mapping = SimpleNamespace(adapter_code="cz_adapter", carrier_code="CZ")
    service = _make_service(mapping=mapping, fallback_enabled=False)
    waybill = SimpleNamespace(
        id=5,
        carrier_code="CZ",
        carrier_prefix="784",
        waybill_no="784-83707805",
        plan=None,
        lifecycle_status=WaybillLifecycleStatus.MONITORING,
    )

    snapshot = _run(service.trigger_query(waybill))

    assert snapshot.adapter_code == "cz_adapter"
    assert snapshot.query_status == QueryStatus.FAILED
    assert specific.calls == ["784-83707805"]
    assert general.calls == []
