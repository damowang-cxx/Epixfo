from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.models.enums import UserRoleCode
from app.services.waybill_service import WaybillService


class FakeDb:
    def __init__(self, receipt_ids=None) -> None:
        self.receipt_ids = receipt_ids or []
        self.executed = []
        self.deleted = None
        self.committed = False

    def scalars(self, _stmt):
        return self.receipt_ids

    def execute(self, stmt):
        self.executed.append(stmt)

    def delete(self, item):
        self.deleted = item

    def commit(self):
        self.committed = True


class FakeRepo:
    def __init__(self, waybill) -> None:
        self.waybill = waybill

    def get(self, waybill_id: int):
        return self.waybill if self.waybill and self.waybill.id == waybill_id else None


def _role(code: UserRoleCode):
    return SimpleNamespace(code=code)


def _user(role: UserRoleCode):
    return SimpleNamespace(id=1, is_superuser=False, roles=[_role(role)])


def _service(waybill, receipt_ids=None):
    service = WaybillService.__new__(WaybillService)
    service.db = FakeDb(receipt_ids)
    service.repo = FakeRepo(waybill)
    return service


def test_route_staff_can_delete_waybill_and_detach_warehouse_bindings() -> None:
    waybill = SimpleNamespace(id=7, waybill_no="784-83707805")
    service = _service(waybill, receipt_ids=[88])

    service.delete(7, _user(UserRoleCode.ROUTE_STAFF))

    assert service.db.deleted is waybill
    assert service.db.committed is True
    assert len(service.db.executed) == 4


def test_customer_service_cannot_delete_waybill() -> None:
    waybill = SimpleNamespace(id=7, waybill_no="784-83707805")
    service = _service(waybill)

    with pytest.raises(HTTPException) as exc_info:
        service.delete(7, _user(UserRoleCode.CUSTOMER_SERVICE))

    assert exc_info.value.status_code == 403
    assert service.db.deleted is None
    assert service.db.committed is False
