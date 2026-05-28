from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.models.enums import UserRoleCode
from app.schemas.waybill import WaybillBulkUpdateRequest
from app.services.waybill_service import WaybillService


class FakeDb:
    def __init__(self) -> None:
        self.rollback_count = 0

    def rollback(self):
        self.rollback_count += 1


class FakeRepo:
    def __init__(self, waybills) -> None:
        self.waybills = {waybill.id: waybill for waybill in waybills}

    def get(self, waybill_id: int):
        return self.waybills.get(waybill_id)


def _role(code: UserRoleCode):
    return SimpleNamespace(code=code)


def _user(role: UserRoleCode):
    return SimpleNamespace(id=1, is_superuser=False, roles=[_role(role)])


def _waybill(waybill_id: int, waybill_no: str):
    return SimpleNamespace(id=waybill_id, waybill_no=waybill_no)


def _service(waybills):
    service = WaybillService.__new__(WaybillService)
    service.db = FakeDb()
    service.repo = FakeRepo(waybills)
    return service


def test_bulk_update_collects_partial_failures(monkeypatch) -> None:
    first = _waybill(1, "176-29600664")
    second = _waybill(2, "176-29600665")
    service = _service([first, second])

    def fake_update(waybill_id, payload, current_user):
        if waybill_id == 2:
            raise HTTPException(status_code=400, detail="invalid_planned_flight_info")
        assert payload.outbound_date.isoformat() == "2026-06-01"
        return service.repo.get(waybill_id)

    monkeypatch.setattr(service, "update", fake_update)

    result = service.bulk_update(
        WaybillBulkUpdateRequest(waybill_ids=[1, 2], field="outbound_date", value="2026-06-01"),
        _user(UserRoleCode.ROUTE_STAFF),
    )

    assert result.success_count == 1
    assert result.failed_count == 1
    assert result.updated_waybills[0].waybill_no == first.waybill_no
    assert result.errors[0].id == 2
    assert result.errors[0].waybill_no == second.waybill_no
    assert result.errors[0].message == "invalid_planned_flight_info"
    assert service.db.rollback_count == 1


def test_bulk_update_rejects_unknown_field() -> None:
    service = _service([])

    with pytest.raises(HTTPException) as exc_info:
        service.bulk_update(
            WaybillBulkUpdateRequest(waybill_ids=[1], field="waybill_no", value="176-29600664"),
            _user(UserRoleCode.ROUTE_STAFF),
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "invalid_bulk_update_field"


def test_customer_service_cannot_bulk_update_waybills() -> None:
    service = _service([_waybill(1, "176-29600664")])

    with pytest.raises(HTTPException) as exc_info:
        service.bulk_update(
            WaybillBulkUpdateRequest(waybill_ids=[1], field="outbound_date", value="2026-06-01"),
            _user(UserRoleCode.CUSTOMER_SERVICE),
        )

    assert exc_info.value.status_code == 403
