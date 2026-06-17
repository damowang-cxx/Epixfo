from __future__ import annotations

from datetime import date, datetime
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.models.enums import UserRoleCode, WaybillLifecycleStatus
from app.schemas.waybill import WaybillCreate, WaybillUpdate
from app.services.waybill_service import WaybillService
from app.utils.datetime_utils import app_timezone
from app.utils.planned_flight import extract_planned_flight_no, parse_planned_flight_filter, parse_planned_flight_info


def _role(code: UserRoleCode):
    return SimpleNamespace(code=code)


def _user() -> SimpleNamespace:
    return SimpleNamespace(id=5, is_superuser=True, roles=[_role(UserRoleCode.ROUTE_STAFF)])


class FakeDb:
    def __init__(self) -> None:
        self.added = []
        self.committed = False

    def add(self, item):
        if getattr(item, "id", None) is None:
            item.id = 7
        self.added.append(item)

    def flush(self):
        return None

    def commit(self):
        self.committed = True

    def scalar(self, _stmt):
        return None


class FakeRepo:
    def __init__(self, waybill=None) -> None:
        self.waybill = waybill

    def get_by_no(self, _waybill_no: str):
        return None

    def get(self, waybill_id: int):
        return self.waybill if self.waybill and self.waybill.id == waybill_id else None


class FakeCarriers:
    def identify_waybill(self, _waybill_no: str):
        return "784", "CZ", "cz_adapter"

    def get_agent(self, _agent_id: int):
        return None


class FakeConsignees:
    def get_contact(self, _contact_id: int):
        return None


class FakeAlerts:
    def create_or_update_active(self, *args, **kwargs):
        return None


def _service(waybill=None) -> WaybillService:
    service = WaybillService.__new__(WaybillService)
    service.db = FakeDb()
    service.repo = FakeRepo(waybill)
    service.carriers = FakeCarriers()
    service.consignees = FakeConsignees()
    service.alerts = FakeAlerts()
    return service


def test_parse_planned_flight_info_uses_current_or_next_month() -> None:
    today = date(2026, 5, 25)

    assert parse_planned_flight_info("QR8943/01", today=today).flight_date == date(2026, 6, 1)
    assert parse_planned_flight_info("QR8943/25", today=today).flight_date == date(2026, 5, 25)
    assert parse_planned_flight_info("QR8943/31", today=today).flight_date == date(2026, 5, 31)
    assert parse_planned_flight_info("qr8943_01", today=today).flight_no == "QR8943"


def test_parse_planned_flight_info_rejects_invalid_values() -> None:
    today = date(2026, 5, 25)

    for value in ["", "/01", "QR8943", "QR8943/00", "QR8943/32"]:
        with pytest.raises(ValueError):
            parse_planned_flight_info(value, today=today)


def test_extract_and_filter_planned_flight_info() -> None:
    today = date(2026, 5, 25)

    assert extract_planned_flight_no("QR8943/01") == "QR8943"
    assert extract_planned_flight_no("qr8943_01") == "QR8943"

    pure_filter = parse_planned_flight_filter("qr8943", today=today)
    assert pure_filter.flight_no == "QR8943"
    assert pure_filter.flight_date is None

    combined_filter = parse_planned_flight_filter("QR8943/01", today=today)
    assert combined_filter.flight_no == "QR8943"
    assert combined_filter.flight_date == date(2026, 6, 1)


def test_create_waybill_parses_planned_flight_info_and_monitor_window(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.waybill_service.local_now",
        lambda: datetime(2026, 5, 25, 8, 0, tzinfo=app_timezone()),
    )
    service = _service()

    waybill = service.create(
        WaybillCreate(
            waybill_no="784-83707805",
            planned_flight_info="QR8943/01",
            planned_route_text="CAN-DOH-AMS",
        ),
        _user(),
    )

    assert waybill.plan.planned_flight_no == "QR8943"
    assert waybill.plan.planned_flight_date == date(2026, 6, 1)
    assert waybill.departure_port == "CAN"
    assert waybill.first_monitor_at.date() == date(2026, 5, 29)
    assert service.db.committed is True


def test_update_waybill_parses_planned_flight_info(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.waybill_service.local_now",
        lambda: datetime(2026, 5, 25, 8, 0, tzinfo=app_timezone()),
    )
    waybill = SimpleNamespace(
        id=7,
        lifecycle_status=WaybillLifecycleStatus.CREATED,
        carrier_code="CZ",
        plan=SimpleNamespace(planned_flight_no="OLD123", planned_flight_date=date(2026, 5, 28)),
        updated_by=None,
        first_monitor_at=None,
        next_query_at=None,
    )
    service = _service(waybill)

    result = service.update(7, WaybillUpdate(planned_flight_info="QR8943_25"), _user())

    assert result.plan.planned_flight_no == "QR8943"
    assert result.plan.planned_flight_date == date(2026, 5, 25)
    assert result.first_monitor_at.date() == date(2026, 5, 22)
    assert service.db.committed is True


def test_update_waybill_rejects_invalid_planned_flight_info(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.waybill_service.local_now",
        lambda: datetime(2026, 5, 25, 8, 0, tzinfo=app_timezone()),
    )
    waybill = SimpleNamespace(
        id=7,
        lifecycle_status=WaybillLifecycleStatus.CREATED,
        carrier_code="CZ",
        plan=SimpleNamespace(planned_flight_no="OLD123", planned_flight_date=date(2026, 5, 28)),
        updated_by=None,
        first_monitor_at=None,
        next_query_at=None,
    )
    service = _service(waybill)

    with pytest.raises(HTTPException) as exc_info:
        service.update(7, WaybillUpdate(planned_flight_info="QR8943/32"), _user())

    assert exc_info.value.detail == "invalid_planned_flight_info"
