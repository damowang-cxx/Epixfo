import asyncio
from types import SimpleNamespace

import pytest

from app.adapters.carrier_query.base import CarrierQueryResult
from app.models.enums import CarrierQueryMethod, QueryStatus, WaybillLifecycleStatus
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
    async def query(self, waybill_no: str):
        return CarrierQueryResult(
            status=QueryStatus.FAILED,
            carrier_code="UNKNOWN",
            adapter_code="general_adapter",
            query_method=CarrierQueryMethod.PROTOCOL,
            error_code="awb_not_found",
            error_message="not found",
        )


def _make_service(mapping):
    service = MonitorService.__new__(MonitorService)
    service.db = _FakeDb()
    service.carriers = SimpleNamespace(get_mapping_by_prefix=lambda prefix: mapping)
    service.alerts = SimpleNamespace(
        handle_query_failure=lambda waybill: None,
        handle_query_success=lambda waybill: None,
        check_after_parse=lambda waybill: None,
    )
    service.lifecycle = SimpleNamespace(update_waybill_lifecycle=lambda waybill: None)
    service.waybills = SimpleNamespace()
    return service


def test_monitor_unknown_waybill_uses_general_adapter(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = _StubAdapter()
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
    adapter = _StubAdapter()
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
