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
        "customs_data_uploaded_at": None,
        "customs_data_uploaded_by": None,
        "updated_by": None,
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


class FakeAlerts:
    def __init__(self) -> None:
        self.resolved = []
        self.checked = []

    def resolve_active(self, waybill, alert_type, user=None):
        self.resolved.append((waybill, alert_type, user))

    def check_customs_data_upload(self, waybill):
        self.checked.append(waybill)


def _service(waybill=None, grant_exists: bool = False):
    service = WaybillService.__new__(WaybillService)
    service.db = FakeDb(grant_exists=grant_exists)
    service.repo = FakeRepo(waybill)
    service.alerts = FakeAlerts()
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


def test_assigned_customs_staff_can_confirm_customs_upload() -> None:
    waybill = _waybill(customs_staff_id=4)
    service = _service(waybill)

    result = service.confirm_customs_data_uploaded(waybill.id, _user(4, UserRoleCode.CUSTOMS_STAFF))

    assert result is waybill
    assert waybill.customs_data_uploaded_at is not None
    assert waybill.customs_data_uploaded_by == 4
    assert service.alerts.resolved[0][1] == "customs_data_not_uploaded_after_departure"
    assert service.db.committed is True


def test_customer_service_cannot_confirm_customs_upload() -> None:
    waybill = _waybill()
    service = _service(waybill)

    with pytest.raises(HTTPException) as exc_info:
        service.confirm_customs_data_uploaded(waybill.id, _user(4, UserRoleCode.CUSTOMER_SERVICE))

    assert exc_info.value.status_code == 403
    assert waybill.customs_data_uploaded_at is None
    assert service.db.committed is False


def test_customs_upload_confirm_requires_warehouse_received_or_later() -> None:
    waybill = _waybill(lifecycle_status=WaybillLifecycleStatus.CREATED)
    service = _service(waybill)

    with pytest.raises(HTTPException) as exc_info:
        service.confirm_customs_data_uploaded(waybill.id, _user(2, UserRoleCode.ROUTE_STAFF))

    assert exc_info.value.status_code == 400
    assert waybill.customs_data_uploaded_at is None


def test_route_staff_can_revoke_customs_upload_and_recheck_alert() -> None:
    waybill = _waybill(customs_data_uploaded_at="2026-05-25T10:00:00Z", customs_data_uploaded_by=4)
    service = _service(waybill)

    result = service.revoke_customs_data_uploaded(waybill.id, _user(2, UserRoleCode.ROUTE_STAFF))

    assert result is waybill
    assert waybill.customs_data_uploaded_at is None
    assert waybill.customs_data_uploaded_by is None
    assert service.alerts.checked == [waybill]
    assert service.db.committed is True
