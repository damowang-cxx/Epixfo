from app.core.platform_patch import patch_platform_wmi

patch_platform_wmi()

from sqlalchemy.orm import Session

from app.models import AirWaybill, WaybillStatusEvent
from app.models.enums import OfficialEventType, WaybillLifecycleStatus
from app.repositories.waybill_repository import WaybillRepository
from app.utils.datetime_utils import compute_next_query_at


LIFECYCLE_PRIORITY = [
    (OfficialEventType.PICKED_UP, WaybillLifecycleStatus.PICKED_UP),
    (OfficialEventType.PICKUP_NOTIFIED, WaybillLifecycleStatus.PICKUP_NOTIFIED),
    (OfficialEventType.FLIGHT_ARRIVED, WaybillLifecycleStatus.ARRIVED),
    (OfficialEventType.FLIGHT_DEPARTED, WaybillLifecycleStatus.DEPARTED),
    (OfficialEventType.CARGO_LOADED, WaybillLifecycleStatus.LOADED),
    (OfficialEventType.ORIGIN_CARGO_RECEIVED, WaybillLifecycleStatus.WAREHOUSE_RECEIVED),
]


class LifecycleService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = WaybillRepository(db)

    def calculate(self, events: list[WaybillStatusEvent]) -> WaybillLifecycleStatus:
        event_types = {event.normalized_event_type for event in events}
        for event_type, lifecycle_status in LIFECYCLE_PRIORITY:
            if event_type in event_types:
                return lifecycle_status
        return WaybillLifecycleStatus.MONITORING

    def update_waybill_lifecycle(self, waybill: AirWaybill) -> WaybillLifecycleStatus:
        if waybill.lifecycle_status == WaybillLifecycleStatus.VOIDED:
            return waybill.lifecycle_status
        events = self.repo.status_events(waybill.id)
        status = self.calculate(events)
        waybill.lifecycle_status = status
        planned_date = waybill.plan.planned_flight_date if waybill.plan else None
        waybill.next_query_at = compute_next_query_at(planned_date, status)
        return status
