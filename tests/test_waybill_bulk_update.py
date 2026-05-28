from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.models.enums import UserRoleCode
from app.schemas.waybill import WaybillBulkDeleteRequest, WaybillBulkInlineUpdateRequest, WaybillBulkUpdateRequest
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

    def get_by_no(self, waybill_no: str):
        return next((waybill for waybill in self.waybills.values() if waybill.waybill_no == waybill_no), None)


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
    service.carriers = SimpleNamespace(identify_waybill=lambda waybill_no: (waybill_no[:3], "TEST", None))
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


def test_apply_waybill_no_update_rejects_duplicate() -> None:
    first = _waybill(1, "176-29600664")
    second = _waybill(2, "176-29600665")
    service = _service([first, second])

    with pytest.raises(HTTPException) as exc_info:
        service._apply_waybill_no_update(first, second.waybill_no)

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "waybill_no_already_exists"


def test_apply_waybill_no_update_reidentifies_carrier() -> None:
    waybill = _waybill(1, "176-29600664")
    waybill.carrier_prefix = "176"
    waybill.carrier_code = "OLD"
    service = _service([waybill])
    service.carriers = SimpleNamespace(identify_waybill=lambda waybill_no: ("999", "NEW", None))

    service._apply_waybill_no_update(waybill, "999-29600664")

    assert waybill.waybill_no == "999-29600664"
    assert waybill.carrier_prefix == "999"
    assert waybill.carrier_code == "NEW"


def test_bulk_inline_update_collects_partial_failures(monkeypatch) -> None:
    first = _waybill(1, "176-29600664")
    second = _waybill(2, "176-29600665")
    service = _service([first, second])

    def fake_update(waybill_id, payload, current_user):
        if waybill_id == 2:
            raise HTTPException(status_code=400, detail="invalid_waybill_no")
        assert payload.waybill_no == "176-29600666"
        return service.repo.get(waybill_id)

    monkeypatch.setattr(service, "update", fake_update)

    updated, errors = service.bulk_inline_update(
        WaybillBulkInlineUpdateRequest(
            updates=[
                {"waybill_id": 1, "changes": {"waybill_no": "176-29600666"}},
                {"waybill_id": 2, "changes": {"waybill_no": ""}},
            ]
        ),
        _user(UserRoleCode.ROUTE_STAFF),
    )

    assert [item.id for item in updated] == [1]
    assert errors[0].waybill_id == 2
    assert errors[0].waybill_no == second.waybill_no
    assert errors[0].message == "invalid_waybill_no"
    assert service.db.rollback_count == 1


def test_bulk_inline_update_rejects_unknown_field() -> None:
    first = _waybill(1, "176-29600664")
    service = _service([first])

    updated, errors = service.bulk_inline_update(
        WaybillBulkInlineUpdateRequest(updates=[{"waybill_id": 1, "changes": {"warehouse_no": "WH-1"}}]),
        _user(UserRoleCode.ROUTE_STAFF),
    )

    assert updated == []
    assert errors[0].field == "warehouse_no"
    assert errors[0].message == "invalid_inline_update_field"


def test_bulk_delete_collects_partial_failures(monkeypatch) -> None:
    first = _waybill(1, "176-29600664")
    second = _waybill(2, "176-29600665")
    service = _service([first, second])

    def fake_delete(waybill_id, current_user):
        if waybill_id == 2:
            raise HTTPException(status_code=400, detail="cannot_delete")

    monkeypatch.setattr(service, "delete", fake_delete)

    result = service.bulk_delete(
        WaybillBulkDeleteRequest(waybill_ids=[1, 2]),
        _user(UserRoleCode.ROUTE_STAFF),
    )

    assert result.success_count == 1
    assert result.deleted_waybills[0].id == 1
    assert result.failed_count == 1
    assert result.errors[0].id == 2
    assert result.errors[0].message == "cannot_delete"
    assert service.db.rollback_count == 1
