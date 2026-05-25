from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.models.enums import UserRoleCode, WaybillLifecycleStatus
from app.services.waybill_service import WaybillService


def _role(code: UserRoleCode):
    return SimpleNamespace(code=code)


def _user(user_id: int, role: UserRoleCode):
    return SimpleNamespace(id=user_id, is_superuser=False, roles=[_role(role)])


def _waybill(**overrides):
    data = {
        "id": 7,
        "waybill_no": "784-83707805",
        "lifecycle_status": WaybillLifecycleStatus.WAREHOUSE_RECEIVED,
        "customs_staff_id": None,
    }
    data.update(overrides)
    return SimpleNamespace(**data)


class FakeDb:
    def __init__(self, grant_exists: bool = False) -> None:
        self.grant_exists = grant_exists
        self.added = []
        self.committed = False

    def scalar(self, _stmt):
        return 1 if self.grant_exists else None

    def add(self, item):
        self.added.append(item)

    def commit(self):
        self.committed = True


class FakeRepo:
    def __init__(self, waybill=None) -> None:
        self.waybill = waybill

    def get(self, waybill_id: int):
        return self.waybill if self.waybill and self.waybill.id == waybill_id else None

    def get_by_no(self, waybill_no: str):
        return self.waybill if self.waybill and self.waybill.waybill_no == waybill_no else None


def _service(waybill=None, grant_exists: bool = False):
    service = WaybillService.__new__(WaybillService)
    service.db = FakeDb(grant_exists=grant_exists)
    service.repo = FakeRepo(waybill)
    return service


def test_assigned_customs_staff_can_view_warehouse_received_waybill() -> None:
    waybill = _waybill(customs_staff_id=4)
    service = _service(waybill)

    assert service.get_visible(waybill.id, _user(4, UserRoleCode.CUSTOMS_STAFF)) is waybill


def test_unassigned_customs_staff_without_grant_cannot_view_waybill() -> None:
    waybill = _waybill(customs_staff_id=5)
    service = _service(waybill, grant_exists=False)

    with pytest.raises(HTTPException) as exc_info:
        service.get_visible(waybill.id, _user(4, UserRoleCode.CUSTOMS_STAFF))

    assert exc_info.value.status_code == 403


def test_customs_access_request_creates_permanent_grant_for_available_waybill() -> None:
    waybill = _waybill()
    service = _service(waybill, grant_exists=False)

    result = service.request_customs_access(waybill.waybill_no, _user(4, UserRoleCode.CUSTOMS_STAFF))

    assert result is waybill
    assert len(service.db.added) == 1
    assert service.db.committed is True


def test_customs_access_request_rejects_waybill_before_warehouse_received() -> None:
    waybill = _waybill(lifecycle_status=WaybillLifecycleStatus.CREATED)
    service = _service(waybill)

    with pytest.raises(HTTPException) as exc_info:
        service.request_customs_access(waybill.waybill_no, _user(4, UserRoleCode.CUSTOMS_STAFF))

    assert exc_info.value.status_code == 400
    assert service.db.added == []
