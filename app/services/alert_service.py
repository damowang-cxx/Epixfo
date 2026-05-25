from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from app.core.platform_patch import patch_platform_wmi

patch_platform_wmi()

from sqlalchemy import exists, or_, select
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.models import AirWaybill, User, WaybillAlert, WaybillCustomsAccessGrant, WaybillOfficialInfo, WaybillStatusEvent
from app.models.enums import AlertLevel, AlertStatus, OfficialEventType, UserRoleCode, WaybillLifecycleStatus
from app.repositories.alert_repository import AlertRepository
from app.repositories.waybill_repository import WaybillRepository
from app.services.permission_service import PermissionService, VISIBLE_TO_CUSTOMER_SERVICE
from app.utils.datetime_utils import local_day_start, local_now, utc_now


ALERT_LEVEL_ORDER = {
    AlertLevel.INFO: 1,
    AlertLevel.WARNING: 2,
    AlertLevel.CRITICAL: 3,
}

CUSTOMS_DATA_NOT_UPLOADED_ALERT = "customs_data_not_uploaded_after_departure"
DEPARTED_OR_AFTER = {
    WaybillLifecycleStatus.DEPARTED,
    WaybillLifecycleStatus.ARRIVED,
    WaybillLifecycleStatus.PICKUP_NOTIFIED,
    WaybillLifecycleStatus.PICKED_UP,
}


class AlertService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = AlertRepository(db)
        self.waybills = WaybillRepository(db)

    def create_or_update_active(
        self,
        waybill: AirWaybill,
        alert_type: str,
        level: AlertLevel,
        title: str,
        description: str | None = None,
        old_value: object | None = None,
        new_value: object | None = None,
    ) -> WaybillAlert:
        alert = self.repo.active_for_type(waybill.id, alert_type)
        if alert is None:
            alert = WaybillAlert(waybill_id=waybill.id, alert_type=alert_type, title=title)
            self.db.add(alert)
        alert.alert_level = level
        alert.title = title
        alert.description = description
        alert.old_value = None if old_value is None else str(old_value)
        alert.new_value = None if new_value is None else str(new_value)
        alert.status = AlertStatus.ACTIVE
        self.update_waybill_alert_level(waybill)
        return alert

    def resolve_active(self, waybill: AirWaybill, alert_type: str, user: User | None = None) -> None:
        alert = self.repo.active_for_type(waybill.id, alert_type)
        if alert:
            alert.status = AlertStatus.RESOLVED
            alert.resolved_at = utc_now()
            alert.resolved_by = user.id if user else None
        self.update_waybill_alert_level(waybill)

    def update_waybill_alert_level(self, waybill: AirWaybill) -> None:
        active_alerts = [alert for alert in self.waybills.alerts(waybill.id) if alert.status == AlertStatus.ACTIVE]
        if not active_alerts:
            waybill.alert_level = None
            return
        waybill.alert_level = max(active_alerts, key=lambda item: ALERT_LEVEL_ORDER[item.alert_level]).alert_level

    def handle_query_failure(self, waybill: AirWaybill) -> None:
        waybill.consecutive_query_failures += 1
        if waybill.consecutive_query_failures >= 5:
            level = AlertLevel.CRITICAL
        elif waybill.consecutive_query_failures >= 3:
            level = AlertLevel.WARNING
        else:
            return
        self.create_or_update_active(
            waybill,
            "query_failed",
            level,
            "航司查询失败",
            f"连续查询失败 {waybill.consecutive_query_failures} 次。",
        )

    def handle_query_success(self, waybill: AirWaybill) -> None:
        waybill.consecutive_query_failures = 0
        self.resolve_active(waybill, "query_failed")

    def list_visible(
        self,
        user: User,
        status: AlertStatus | None = None,
        alert_type: str | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[WaybillAlert]:
        roles = PermissionService.role_codes(user)
        if UserRoleCode.ADMIN.value in roles or UserRoleCode.ROUTE_STAFF.value in roles:
            return self.repo.list(status=status, alert_type=alert_type, skip=skip, limit=limit)
        if UserRoleCode.CUSTOMS_STAFF.value not in roles:
            return []

        granted = exists().where(
            WaybillCustomsAccessGrant.waybill_id == AirWaybill.id,
            WaybillCustomsAccessGrant.user_id == user.id,
        )
        query = (
            select(WaybillAlert)
            .options(selectinload(WaybillAlert.waybill))
            .join(AirWaybill, AirWaybill.id == WaybillAlert.waybill_id)
            .where(
                AirWaybill.lifecycle_status.in_(VISIBLE_TO_CUSTOMER_SERVICE),
                or_(AirWaybill.customs_staff_id == user.id, granted),
            )
            .order_by(WaybillAlert.id.desc())
        )
        if status:
            query = query.where(WaybillAlert.status == status)
        if alert_type:
            query = query.where(WaybillAlert.alert_type == alert_type)
        return list(self.db.scalars(query.offset(skip).limit(limit)))

    def check_customs_data_upload(self, waybill: AirWaybill) -> None:
        if waybill.lifecycle_status not in DEPARTED_OR_AFTER or waybill.lifecycle_status == WaybillLifecycleStatus.VOIDED:
            self.resolve_active(waybill, CUSTOMS_DATA_NOT_UPLOADED_ALERT)
            return
        if waybill.customs_data_uploaded_at is not None:
            self.resolve_active(waybill, CUSTOMS_DATA_NOT_UPLOADED_ALERT)
            return
        self.create_or_update_active(
            waybill,
            CUSTOMS_DATA_NOT_UPLOADED_ALERT,
            AlertLevel.CRITICAL,
            "清关资料未上传",
            description="提单已起飞，但系统尚未确认清关资料已上传到清关行。",
        )

    def check_after_parse(self, waybill: AirWaybill) -> None:
        if not waybill.plan:
            return
        segments = self.waybills.official_segments(waybill.id)
        events = self.waybills.status_events(waybill.id)
        official_info = self.waybills.official_info(waybill.id)

        planned_flight_no = waybill.plan.planned_flight_no
        planned_flight_date = waybill.plan.planned_flight_date
        planned_route = waybill.plan.planned_route_text

        if planned_flight_no and segments and planned_flight_no not in {segment.flight_no for segment in segments}:
            self.create_or_update_active(
                waybill,
                "flight_no_changed",
                AlertLevel.WARNING,
                "航班号变化",
                old_value=planned_flight_no,
                new_value=", ".join(sorted({str(segment.flight_no) for segment in segments if segment.flight_no})),
            )

        if planned_flight_date and segments and planned_flight_date not in {segment.flight_date for segment in segments}:
            self.create_or_update_active(
                waybill,
                "flight_date_changed",
                AlertLevel.WARNING,
                "航班日期变化",
                old_value=planned_flight_date,
                new_value=", ".join(sorted({str(segment.flight_date) for segment in segments if segment.flight_date})),
            )

        if planned_route and official_info and official_info.route_text and planned_route not in official_info.route_text:
            self.create_or_update_active(
                waybill,
                "route_changed",
                AlertLevel.WARNING,
                "航程变化",
                old_value=planned_route,
                new_value=official_info.route_text,
            )

        self._check_not_departed(waybill, events)
        self._check_not_received(waybill, events)
        self._check_weight_volume(waybill, official_info)
        self.check_customs_data_upload(waybill)
        self.update_waybill_alert_level(waybill)

    def _check_not_departed(self, waybill: AirWaybill, events: list[WaybillStatusEvent]) -> None:
        planned_date = waybill.plan.planned_flight_date if waybill.plan else None
        if not planned_date:
            return
        if local_now() <= local_day_start(planned_date + timedelta(days=1)):
            return
        if not any(event.normalized_event_type == OfficialEventType.FLIGHT_DEPARTED for event in events):
            self.create_or_update_active(
                waybill,
                "not_departed_on_planned_date",
                AlertLevel.CRITICAL,
                "计划日期结束后仍未起飞",
            )

    def _check_not_received(self, waybill: AirWaybill, events: list[WaybillStatusEvent]) -> None:
        planned_date = waybill.plan.planned_flight_date if waybill.plan else None
        if not planned_date:
            return
        if local_now() <= local_day_start(planned_date):
            return
        if not any(event.normalized_event_type == OfficialEventType.ORIGIN_CARGO_RECEIVED for event in events):
            self.create_or_update_active(
                waybill,
                "not_received_before_departure",
                AlertLevel.WARNING,
                "航班日前一天仍未入仓",
            )

    def _diff_exceeds(self, planned: Decimal | None, official: Decimal | None, abs_threshold: float, pct_threshold: float) -> bool:
        if planned is None or official is None:
            return False
        diff = abs(official - planned)
        threshold = max(Decimal(str(abs_threshold)), abs(planned) * Decimal(str(pct_threshold)))
        return diff > threshold

    def _check_weight_volume(self, waybill: AirWaybill, official_info: WaybillOfficialInfo | None) -> None:
        if official_info is None:
            return
        if self._diff_exceeds(
            waybill.booked_weight,
            official_info.total_weight,
            settings.weight_mismatch_absolute_threshold,
            settings.weight_mismatch_percent_threshold,
        ):
            self.create_or_update_active(
                waybill,
                "official_weight_mismatch",
                AlertLevel.WARNING,
                "官网重量与人工订舱重量差异较大",
                old_value=waybill.booked_weight,
                new_value=official_info.total_weight,
            )
        if self._diff_exceeds(
            waybill.booked_volume,
            official_info.total_volume,
            settings.volume_mismatch_absolute_threshold,
            settings.volume_mismatch_percent_threshold,
        ):
            self.create_or_update_active(
                waybill,
                "official_volume_mismatch",
                AlertLevel.WARNING,
                "官网体积与人工订舱方数差异较大",
                old_value=waybill.booked_volume,
                new_value=official_info.total_volume,
            )

    def transition(self, alert_id: int, status: AlertStatus, user: User) -> WaybillAlert | None:
        alert = self.repo.get(alert_id)
        if alert is None:
            return None
        alert.status = status
        if status == AlertStatus.ACKNOWLEDGED:
            alert.acknowledged_by = user.id
            alert.acknowledged_at = utc_now()
        if status == AlertStatus.RESOLVED:
            alert.resolved_by = user.id
            alert.resolved_at = utc_now()
        waybill = self.waybills.get(alert.waybill_id)
        if waybill:
            self.update_waybill_alert_level(waybill)
        self.db.commit()
        self.db.refresh(alert)
        return alert
