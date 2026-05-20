from __future__ import annotations

from datetime import date, datetime, timedelta

from app.core.platform_patch import patch_platform_wmi

patch_platform_wmi()

from sqlalchemy.orm import Session

from app.core.exceptions import bad_request, forbidden, not_found
from app.models import AirWaybill, User, WaybillPlan
from app.models.enums import AlertLevel, UserRoleCode, WaybillLifecycleStatus
from app.repositories.waybill_repository import WaybillRepository
from app.schemas.waybill import ManualStatusRequest, WaybillCreate, WaybillUpdate
from app.services.alert_service import AlertService
from app.services.carrier_service import CarrierService
from app.services.monitor_service import MonitorService
from app.services.permission_service import PermissionService, VISIBLE_TO_CUSTOMER_SERVICE
from app.utils.datetime_utils import compute_monitor_window, compute_next_query_at, local_now
from app.utils.pagination import normalize_pagination
from app.utils.waybill_utils import normalize_waybill_no, validate_waybill_no


PLAN_FIELDS = {"planned_flight_no", "planned_flight_date", "planned_destination", "planned_route_text"}


class WaybillService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = WaybillRepository(db)
        self.carriers = CarrierService(db)
        self.alerts = AlertService(db)

    def create(self, payload: WaybillCreate, current_user: User) -> AirWaybill:
        PermissionService.assert_waybill_write(current_user)
        waybill_no = normalize_waybill_no(payload.waybill_no)
        if not validate_waybill_no(waybill_no):
            raise bad_request("Invalid waybill number")
        if self.repo.get_by_no(waybill_no):
            raise bad_request("Waybill already exists")

        prefix, carrier_code, _adapter_code = self.carriers.identify_waybill(waybill_no)
        plan_data = {field: getattr(payload, field) for field in PLAN_FIELDS}
        first_monitor_at, next_query_at = compute_monitor_window(plan_data.get("planned_flight_date"))
        monitor_enabled = carrier_code != "UNKNOWN"
        lifecycle_status = WaybillLifecycleStatus.CREATED
        if monitor_enabled and first_monitor_at:
            lifecycle_status = WaybillLifecycleStatus.WAITING_MONITOR if local_now() < first_monitor_at else WaybillLifecycleStatus.MONITORING

        waybill_data = payload.model_dump(exclude=set(PLAN_FIELDS) | {"waybill_no"}, exclude_none=True)
        waybill = AirWaybill(
            **waybill_data,
            waybill_no=waybill_no,
            carrier_prefix=prefix,
            carrier_code=carrier_code,
            lifecycle_status=lifecycle_status,
            monitor_enabled=monitor_enabled,
            first_monitor_at=first_monitor_at,
            next_query_at=next_query_at if monitor_enabled else None,
            created_by=current_user.id,
            updated_by=current_user.id,
        )
        waybill.plan = WaybillPlan(**plan_data)
        self.db.add(waybill)
        self.db.flush()
        if carrier_code == "UNKNOWN":
            self.alerts.create_or_update_active(
                waybill,
                "carrier_unknown",
                AlertLevel.WARNING,
                "运单前三位无法识别航司",
                description=f"运单前缀 {prefix} 未配置航司映射。",
            )
        self.db.commit()
        return self.repo.get(waybill.id) or waybill

    def update(self, waybill_id: int, payload: WaybillUpdate, current_user: User) -> AirWaybill:
        PermissionService.assert_waybill_write(current_user)
        waybill = self.get_visible(waybill_id, current_user)
        if waybill.lifecycle_status == WaybillLifecycleStatus.VOIDED:
            raise bad_request("Voided waybill cannot be updated")
        data = payload.model_dump(exclude_unset=True)
        plan_data = {key: data.pop(key) for key in list(data.keys()) if key in PLAN_FIELDS}
        for key, value in data.items():
            if key in {"include_tc", "notify_pickup"} and value is None:
                continue
            setattr(waybill, key, value)
        if plan_data:
            if waybill.plan is None:
                waybill.plan = WaybillPlan(**plan_data)
            else:
                for key, value in plan_data.items():
                    setattr(waybill.plan, key, value)
            planned_date = waybill.plan.planned_flight_date
            waybill.first_monitor_at, initial_next = compute_monitor_window(planned_date)
            waybill.next_query_at = compute_next_query_at(planned_date, waybill.lifecycle_status) or initial_next
        waybill.updated_by = current_user.id
        self.db.commit()
        return self.repo.get(waybill.id) or waybill

    def get_visible(self, waybill_id: int, current_user: User) -> AirWaybill:
        waybill = self.repo.get(waybill_id)
        if waybill is None:
            raise not_found("Waybill not found")
        roles = PermissionService.role_codes(current_user)
        if UserRoleCode.ADMIN.value in roles or UserRoleCode.ROUTE_STAFF.value in roles:
            return waybill
        if UserRoleCode.CUSTOMER_SERVICE.value in roles and waybill.lifecycle_status in VISIBLE_TO_CUSTOMER_SERVICE:
            return waybill
        if UserRoleCode.CUSTOMS_STAFF.value in roles and waybill.plan and waybill.plan.planned_flight_date:
            today = local_now().date()
            if today <= waybill.plan.planned_flight_date <= today + timedelta(days=3):
                return waybill
        raise forbidden()
        return waybill

    def list(
        self,
        current_user: User,
        page: int = 1,
        page_size: int = 20,
        waybill_no: str | None = None,
        carrier_code: str | None = None,
        destination_port: str | None = None,
        planned_flight_no: str | None = None,
        planned_flight_date_from: date | None = None,
        planned_flight_date_to: date | None = None,
        lifecycle_status: WaybillLifecycleStatus | None = None,
        alert_level: AlertLevel | None = None,
        created_at_from: datetime | None = None,
        created_at_to: datetime | None = None,
    ) -> tuple[list[AirWaybill], int, int, int]:
        pagination = normalize_pagination(page, page_size)
        query = self.repo.base_query()
        query = PermissionService.filter_waybill_query(query, current_user)
        query = self.repo.apply_filters(
            query,
            waybill_no=waybill_no,
            carrier_code=carrier_code,
            destination_port=destination_port,
            planned_flight_no=planned_flight_no,
            planned_flight_date_from=planned_flight_date_from,
            planned_flight_date_to=planned_flight_date_to,
            lifecycle_status=lifecycle_status,
            alert_level=alert_level,
            created_at_from=created_at_from,
            created_at_to=created_at_to,
        )
        total = self.repo.count_filtered(query)
        return self.repo.list_filtered(query, pagination.offset, pagination.page_size), total, pagination.page, pagination.page_size

    def void(self, waybill_id: int, current_user: User) -> AirWaybill:
        PermissionService.require_any(current_user, {UserRoleCode.ADMIN})
        waybill = self.repo.get(waybill_id)
        if waybill is None:
            raise not_found("Waybill not found")
        waybill.lifecycle_status = WaybillLifecycleStatus.VOIDED
        waybill.monitor_enabled = False
        waybill.next_query_at = None
        waybill.updated_by = current_user.id
        self.db.commit()
        return self.repo.get(waybill.id) or waybill

    def manual_status(self, waybill_id: int, payload: ManualStatusRequest, current_user: User) -> AirWaybill:
        PermissionService.require_any(current_user, {UserRoleCode.ADMIN})
        waybill = self.repo.get(waybill_id)
        if waybill is None:
            raise not_found("Waybill not found")
        waybill.lifecycle_status = payload.lifecycle_status
        waybill.next_query_at = compute_next_query_at(
            waybill.plan.planned_flight_date if waybill.plan else None,
            payload.lifecycle_status,
        )
        waybill.updated_by = current_user.id
        self.db.commit()
        return self.repo.get(waybill.id) or waybill

    async def trigger_query(self, waybill_id: int, current_user: User):
        PermissionService.assert_waybill_write(current_user)
        waybill = self.repo.get(waybill_id)
        if waybill is None:
            raise not_found("Waybill not found")
        return await MonitorService(self.db).trigger_query(waybill)
