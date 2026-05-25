from types import SimpleNamespace

from app.models.enums import AlertStatus, WaybillLifecycleStatus
from app.services.alert_service import AlertService, CUSTOMS_DATA_NOT_UPLOADED_ALERT


class FakeDb:
    def __init__(self) -> None:
        self.added = []

    def add(self, item):
        self.added.append(item)


class FakeAlertRepository:
    def __init__(self, active=None) -> None:
        self.active = active

    def active_for_type(self, waybill_id: int, alert_type: str):
        if self.active and self.active.waybill_id == waybill_id and self.active.alert_type == alert_type:
            return self.active
        return None


class FakeWaybillRepository:
    def __init__(self, alerts=None) -> None:
        self._alerts = alerts or []

    def alerts(self, waybill_id: int):
        return [alert for alert in self._alerts if alert.waybill_id == waybill_id]


def _service(active=None, alerts=None):
    service = AlertService.__new__(AlertService)
    service.db = FakeDb()
    service.repo = FakeAlertRepository(active)
    service.waybills = FakeWaybillRepository(alerts)
    return service


def _waybill(**overrides):
    data = {
        "id": 7,
        "waybill_no": "784-83707805",
        "lifecycle_status": WaybillLifecycleStatus.DEPARTED,
        "customs_data_uploaded_at": None,
        "alert_level": None,
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def test_departed_waybill_without_customs_upload_creates_critical_alert() -> None:
    service = _service()
    waybill = _waybill()

    service.check_customs_data_upload(waybill)

    assert len(service.db.added) == 1
    alert = service.db.added[0]
    assert alert.alert_type == CUSTOMS_DATA_NOT_UPLOADED_ALERT
    assert alert.alert_level == "critical"
    assert alert.status == "active"
    assert "清关资料" in alert.title


def test_customs_upload_resolves_existing_alert() -> None:
    alert = SimpleNamespace(
        waybill_id=7,
        alert_type=CUSTOMS_DATA_NOT_UPLOADED_ALERT,
        status=AlertStatus.ACTIVE,
        resolved_at=None,
        resolved_by=None,
        alert_level="critical",
    )
    service = _service(active=alert, alerts=[alert])
    waybill = _waybill(customs_data_uploaded_at="2026-05-25T10:00:00Z")

    service.check_customs_data_upload(waybill)

    assert alert.status == AlertStatus.RESOLVED
    assert alert.resolved_at is not None
