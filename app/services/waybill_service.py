from __future__ import annotations

from datetime import date, datetime

from app.core.platform_patch import patch_platform_wmi

patch_platform_wmi()

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import select, update
from sqlalchemy.orm import Session, selectinload

from app.core.exceptions import bad_request, forbidden, not_found
from app.models import AirWaybill, Box, BoxDocument, User, WarehouseReceipt, WaybillCustomsAccessGrant, WaybillPlan, WaybillViewLog
from app.models.enums import AlertLevel, UserRoleCode, WaybillLifecycleStatus
from app.repositories.waybill_repository import WaybillRepository
from app.schemas.waybill import (
    ManualStatusRequest,
    WaybillBulkUpdateError,
    WaybillBulkUpdateItem,
    WaybillBulkUpdateRequest,
    WaybillBulkUpdateResult,
    WaybillCreate,
    WaybillStatusCount,
    WaybillUpdate,
)
from app.services.alert_service import AlertService
from app.services.carrier_service import CarrierService
from app.services.consignee_service import ConsigneeService
from app.services.monitor_service import MonitorService
from app.services.permission_service import PermissionService, VISIBLE_TO_CUSTOMER_SERVICE
from app.utils.datetime_utils import compute_monitor_window, compute_next_query_at, local_now, utc_now
from app.utils.pagination import normalize_pagination
from app.utils.planned_flight import parse_planned_flight_filter, parse_planned_flight_info
from app.utils.waybill_utils import normalize_waybill_no, validate_waybill_no


PLAN_FIELDS = {"planned_flight_no", "planned_flight_date", "planned_destination", "planned_route_text"}
PLAN_INPUT_FIELDS = PLAN_FIELDS | {"planned_flight_info"}
WAYBILL_BULK_UPDATE_FIELDS = {
    "customs_staff_id",
    "outbound_date",
    "carrier_agent_id",
    "consignee_contact_id",
    "departure_port",
    "destination_port",
    "planned_flight_info",
    "planned_route_text",
    "warehouse_data_remark",
    "customer_remark",
    "internal_remark",
}


class WaybillService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = WaybillRepository(db)
        self.carriers = CarrierService(db)
        self.consignees = ConsigneeService(db)
        self.alerts = AlertService(db)

    def create(self, payload: WaybillCreate, current_user: User) -> AirWaybill:
        PermissionService.assert_waybill_write(current_user)
        waybill_no = normalize_waybill_no(payload.waybill_no)
        if not validate_waybill_no(waybill_no):
            raise bad_request("Invalid waybill number")
        if self.repo.get_by_no(waybill_no):
            raise bad_request("Waybill already exists")

        prefix, carrier_code, _adapter_code = self.carriers.identify_waybill(waybill_no)
        agent_snapshot = self._resolve_agent_snapshot(payload.carrier_agent_id, carrier_code)
        consignee_snapshot = self._resolve_consignee_snapshot(payload.consignee_contact_id)
        self._validate_customs_staff_id(payload.customs_staff_id)
        plan_data = self._plan_data_from_payload(payload)
        first_monitor_at, next_query_at = compute_monitor_window(plan_data.get("planned_flight_date"))
        monitor_enabled = True
        lifecycle_status = WaybillLifecycleStatus.CREATED
        if monitor_enabled and first_monitor_at:
            lifecycle_status = WaybillLifecycleStatus.WAITING_MONITOR if local_now() < first_monitor_at else WaybillLifecycleStatus.MONITORING

        waybill_data = payload.model_dump(
            exclude=PLAN_INPUT_FIELDS | {"waybill_no", "carrier_agent_id", "consignee_contact_id", "consignee"},
            exclude_none=True,
        )
        waybill = AirWaybill(
            **waybill_data,
            waybill_no=waybill_no,
            carrier_prefix=prefix,
            carrier_code=carrier_code,
            carrier_agent_id=agent_snapshot[0] if agent_snapshot else None,
            agent=agent_snapshot[1] if agent_snapshot else None,
            consignee_contact_id=consignee_snapshot[0] if consignee_snapshot else None,
            consignee=consignee_snapshot[1] if consignee_snapshot else payload.consignee,
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
        plan_data = self._plan_data_from_update_data(data)
        if "carrier_agent_id" in data:
            agent_snapshot = self._resolve_agent_snapshot(data.pop("carrier_agent_id"), waybill.carrier_code)
            if agent_snapshot is None:
                waybill.carrier_agent_id = None
                waybill.agent = None
            else:
                waybill.carrier_agent_id, waybill.agent = agent_snapshot
        if "consignee_contact_id" in data:
            consignee_snapshot = self._resolve_consignee_snapshot(data.pop("consignee_contact_id"))
            if consignee_snapshot is None:
                waybill.consignee_contact_id = None
                # 不强清 consignee 文本，可能是手填 / 历史快照
                if "consignee" not in data:
                    waybill.consignee = None
            else:
                waybill.consignee_contact_id, waybill.consignee = consignee_snapshot
        if "customs_staff_id" in data:
            self._validate_customs_staff_id(data["customs_staff_id"])
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

    def bulk_update(self, payload: WaybillBulkUpdateRequest, current_user: User) -> WaybillBulkUpdateResult:
        PermissionService.assert_waybill_write(current_user)
        if payload.field not in WAYBILL_BULK_UPDATE_FIELDS:
            raise bad_request("invalid_bulk_update_field")

        updated: list[WaybillBulkUpdateItem] = []
        errors: list[WaybillBulkUpdateError] = []
        for waybill_id in payload.waybill_ids:
            try:
                update_payload = WaybillUpdate.model_validate({payload.field: payload.value})
                waybill = self.update(waybill_id, update_payload, current_user)
                updated.append(WaybillBulkUpdateItem(id=waybill.id, waybill_no=waybill.waybill_no))
            except ValidationError as exc:
                self.db.rollback()
                errors.append(
                    WaybillBulkUpdateError(
                        id=waybill_id,
                        waybill_no=self._safe_waybill_no(waybill_id),
                        message=exc.errors()[0].get("msg", "invalid_value") if exc.errors() else "invalid_value",
                    )
                )
            except HTTPException as exc:
                self.db.rollback()
                errors.append(
                    WaybillBulkUpdateError(
                        id=waybill_id,
                        waybill_no=self._safe_waybill_no(waybill_id),
                        message=str(exc.detail),
                    )
                )
            except Exception as exc:
                self.db.rollback()
                errors.append(
                    WaybillBulkUpdateError(
                        id=waybill_id,
                        waybill_no=self._safe_waybill_no(waybill_id),
                        message=str(exc) or "update_failed",
                    )
                )

        return WaybillBulkUpdateResult(
            success_count=len(updated),
            failed_count=len(errors),
            updated_waybills=updated,
            errors=errors,
        )

    def _safe_waybill_no(self, waybill_id: int) -> str | None:
        try:
            waybill = self.repo.get(waybill_id)
        except Exception:
            return None
        return waybill.waybill_no if waybill else None

    def get_visible(self, waybill_id: int, current_user: User) -> AirWaybill:
        waybill = self.repo.get(waybill_id)
        if waybill is None:
            raise not_found("Waybill not found")
        roles = PermissionService.role_codes(current_user)
        if UserRoleCode.ADMIN.value in roles or UserRoleCode.ROUTE_STAFF.value in roles:
            return waybill
        if UserRoleCode.CUSTOMER_SERVICE.value in roles and waybill.lifecycle_status in VISIBLE_TO_CUSTOMER_SERVICE:
            return waybill
        if UserRoleCode.CUSTOMS_STAFF.value in roles and waybill.lifecycle_status in VISIBLE_TO_CUSTOMER_SERVICE:
            if waybill.customs_staff_id == current_user.id or self._has_customs_access(waybill.id, current_user.id):
                return waybill
        raise forbidden()
        return waybill

    def request_customs_access(self, waybill_no: str, current_user: User) -> AirWaybill:
        PermissionService.require_any(current_user, {UserRoleCode.CUSTOMS_STAFF})
        normalized_no = normalize_waybill_no(waybill_no)
        waybill = self.repo.get_by_no(normalized_no)
        if waybill is None:
            raise not_found("Waybill not found")
        if waybill.lifecycle_status == WaybillLifecycleStatus.VOIDED:
            raise bad_request("voided_waybill_not_available")
        if waybill.lifecycle_status not in VISIBLE_TO_CUSTOMER_SERVICE:
            raise bad_request("waybill_not_available_for_customs")
        if waybill.customs_staff_id != current_user.id and not self._has_customs_access(waybill.id, current_user.id):
            self.db.add(WaybillCustomsAccessGrant(waybill_id=waybill.id, user_id=current_user.id))
            self.db.commit()
        return self.repo.get(waybill.id) or waybill

    def confirm_customs_data_uploaded(self, waybill_id: int, current_user: User) -> AirWaybill:
        roles = PermissionService.role_codes(current_user)
        if UserRoleCode.ADMIN.value not in roles and UserRoleCode.ROUTE_STAFF.value not in roles:
            PermissionService.require_any(current_user, {UserRoleCode.CUSTOMS_STAFF})
        waybill = self.get_visible(waybill_id, current_user)
        if waybill.lifecycle_status == WaybillLifecycleStatus.VOIDED:
            raise bad_request("voided_waybill_not_available")
        if waybill.lifecycle_status not in VISIBLE_TO_CUSTOMER_SERVICE:
            raise bad_request("waybill_not_ready_for_customs_upload")
        waybill.customs_data_uploaded_at = utc_now()
        waybill.customs_data_uploaded_by = current_user.id
        waybill.updated_by = current_user.id
        self.alerts.resolve_active(waybill, "customs_data_not_uploaded_after_departure", current_user)
        self.db.commit()
        return self.repo.get(waybill.id) or waybill

    def revoke_customs_data_uploaded(self, waybill_id: int, current_user: User) -> AirWaybill:
        PermissionService.assert_waybill_write(current_user)
        waybill = self.get_visible(waybill_id, current_user)
        if waybill.lifecycle_status == WaybillLifecycleStatus.VOIDED:
            raise bad_request("voided_waybill_not_available")
        waybill.customs_data_uploaded_at = None
        waybill.customs_data_uploaded_by = None
        waybill.updated_by = current_user.id
        self.alerts.check_customs_data_upload(waybill)
        self.db.commit()
        return self.repo.get(waybill.id) or waybill

    def record_view(self, waybill: AirWaybill, current_user: User, ip_address: str | None, user_agent: str | None) -> None:
        self.db.add(
            WaybillViewLog(
                user_id=current_user.id,
                waybill_id=waybill.id,
                waybill_no=waybill.waybill_no,
                lifecycle_status=waybill.lifecycle_status,
                ip_address=ip_address,
                user_agent=user_agent,
            )
        )
        self.db.commit()

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
        if planned_flight_no:
            try:
                flight_filter = parse_planned_flight_filter(planned_flight_no, today=local_now().date())
            except ValueError as exc:
                raise bad_request("invalid_planned_flight_info") from exc
            planned_flight_no = flight_filter.flight_no
            if flight_filter.flight_date is not None:
                planned_flight_date_from = flight_filter.flight_date
                planned_flight_date_to = flight_filter.flight_date
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

    def _plan_data_from_payload(self, payload: WaybillCreate | WaybillUpdate) -> dict[str, object]:
        plan_data = {field: getattr(payload, field) for field in PLAN_FIELDS}
        flight_info = getattr(payload, "planned_flight_info", None)
        if flight_info:
            try:
                parsed = parse_planned_flight_info(flight_info, today=local_now().date())
            except ValueError as exc:
                raise bad_request("invalid_planned_flight_info") from exc
            plan_data["planned_flight_no"] = parsed.flight_no
            plan_data["planned_flight_date"] = parsed.flight_date
        else:
            self._normalize_combined_planned_flight_no(plan_data)
        return plan_data

    def _plan_data_from_update_data(self, data: dict[str, object]) -> dict[str, object]:
        plan_data = {key: data.pop(key) for key in list(data.keys()) if key in PLAN_FIELDS}
        if "planned_flight_info" not in data:
            self._normalize_combined_planned_flight_no(plan_data)
            return plan_data

        flight_info = data.pop("planned_flight_info")
        if flight_info is None or str(flight_info).strip() == "":
            plan_data["planned_flight_no"] = None
            plan_data["planned_flight_date"] = None
            return plan_data

        try:
            parsed = parse_planned_flight_info(str(flight_info), today=local_now().date())
        except ValueError as exc:
            raise bad_request("invalid_planned_flight_info") from exc
        plan_data["planned_flight_no"] = parsed.flight_no
        plan_data["planned_flight_date"] = parsed.flight_date
        return plan_data

    def _normalize_combined_planned_flight_no(self, plan_data: dict[str, object]) -> None:
        flight_no = plan_data.get("planned_flight_no")
        if not isinstance(flight_no, str) or ("/" not in flight_no and "_" not in flight_no):
            return
        try:
            parsed = parse_planned_flight_info(flight_no, today=local_now().date())
        except ValueError:
            return
        plan_data["planned_flight_no"] = parsed.flight_no
        if plan_data.get("planned_flight_date") is None:
            plan_data["planned_flight_date"] = parsed.flight_date

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

    def delete(self, waybill_id: int, current_user: User) -> None:
        PermissionService.assert_waybill_write(current_user)
        waybill = self.repo.get(waybill_id)
        if waybill is None:
            raise not_found("Waybill not found")
        self._detach_warehouse_bindings(waybill.id)
        self.db.delete(waybill)
        self.db.commit()

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
        self.alerts.check_customs_data_upload(waybill)
        self.db.commit()
        return self.repo.get(waybill.id) or waybill

    def status_counts(self, current_user: User) -> list[WaybillStatusCount]:
        """按生命周期状态聚合当前角色可见的运单数量。

        全集返回所有生命周期状态（缺失为 0），顺序与 `WaybillLifecycleStatus` 枚举一致。
        """
        query = self.repo.base_query()
        query = PermissionService.filter_waybill_query(query, current_user)
        counts_by_status = self.repo.count_by_status(query)
        return [
            WaybillStatusCount(status=status, count=counts_by_status.get(status, 0))
            for status in WaybillLifecycleStatus
        ]

    async def trigger_query(self, waybill_id: int, current_user: User):
        PermissionService.assert_waybill_write(current_user)
        waybill = self.repo.get(waybill_id)
        if waybill is None:
            raise not_found("Waybill not found")
        return await MonitorService(self.db).trigger_query(waybill)

    def _detach_warehouse_bindings(self, waybill_id: int) -> None:
        receipt_ids = list(
            self.db.scalars(
                select(WarehouseReceipt.id).where(WarehouseReceipt.waybill_id == waybill_id)
            )
        )
        if receipt_ids:
            self.db.execute(
                update(Box)
                .where(Box.warehouse_receipt_id.in_(receipt_ids))
                .values(
                    current_waybill_id=None,
                    status="unbound",
                    never_bound_direct_upload=False,
                    unbound_reason=None,
                    unbound_remark=None,
                )
            )
            self.db.execute(
                update(WarehouseReceipt)
                .where(WarehouseReceipt.id.in_(receipt_ids))
                .values(
                    waybill_id=None,
                )
            )
        self.db.execute(
            update(Box)
            .where(Box.current_waybill_id == waybill_id)
            .values(
                current_waybill_id=None,
                status="unbound",
                never_bound_direct_upload=False,
                unbound_reason=None,
                unbound_remark=None,
            )
        )
        self.db.execute(
            update(BoxDocument)
            .where(BoxDocument.bound_waybill_id == waybill_id)
            .values(bound_waybill_id=None)
        )

    def _resolve_agent_snapshot(
        self,
        carrier_agent_id: int | None,
        carrier_code: str | None,
    ) -> tuple[int, str] | None:
        """根据 carrier_agent_id 查代理实体，返回 (id, agent_name) 快照对。None 表示未指定。"""
        if carrier_agent_id is None:
            return None
        agent = self.carriers.get_agent(carrier_agent_id)
        if agent is None:
            raise bad_request("carrier_agent_not_found")
        if carrier_code and agent.carrier_code != carrier_code:
            raise bad_request("carrier_agent_carrier_mismatch")
        return agent.id, agent.agent_name

    def _resolve_consignee_snapshot(
        self,
        consignee_contact_id: int | None,
    ) -> tuple[int, str] | None:
        """根据 consignee_contact_id 查收件人记录，返回 (id, 厂商名作为快照) 元组。

        None 表示未指定（不动 consignee 字段，保留前端可能手填的文本）。
        """
        if consignee_contact_id is None:
            return None
        contact = self.consignees.get_contact(consignee_contact_id)
        if contact is None:
            raise bad_request("consignee_contact_not_found")
        snapshot_source = contact.name or (contact.consignee.name if contact.consignee else "")
        snapshot = snapshot_source[:255]
        return contact.id, snapshot

    def _validate_customs_staff_id(self, customs_staff_id: int | None) -> None:
        if customs_staff_id is None:
            return
        user = self.db.scalar(select(User).options(selectinload(User.roles)).where(User.id == customs_staff_id))
        if user is None:
            raise bad_request("customs_staff_not_found")
        if not user.is_active or not PermissionService.has_role(user, UserRoleCode.CUSTOMS_STAFF):
            raise bad_request("invalid_customs_staff")

    def _has_customs_access(self, waybill_id: int, user_id: int) -> bool:
        return bool(
            self.db.scalar(
                select(WaybillCustomsAccessGrant.id).where(
                    WaybillCustomsAccessGrant.waybill_id == waybill_id,
                    WaybillCustomsAccessGrant.user_id == user_id,
                )
            )
        )
