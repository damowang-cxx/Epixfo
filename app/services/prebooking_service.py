from __future__ import annotations

from datetime import date

from app.core.platform_patch import patch_platform_wmi

patch_platform_wmi()

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session, selectinload

from app.core.exceptions import bad_request, not_found
from app.models import Box, CarrierAgent, User, WarehouseReceipt, WaybillPrebooking
from app.schemas.box import WarehouseReceiptListOut
from app.schemas.prebooking import WaybillPrebookingCreate, WaybillPrebookingOut, WaybillPrebookingUpdate
from app.schemas.waybill import WaybillCreate
from app.services.permission_service import PermissionService
from app.services.warehouse_file_service import WarehouseFileService
from app.services.waybill_service import WaybillService
from app.utils.pagination import normalize_pagination


PREBOOKING_FIELDS = {
    "carrier_agent_id",
    "planned_flight_date",
    "booked_volume",
    "waybill_no",
    "departure_port",
    "destination_port",
    "planned_flight_no",
    "planned_route_text",
    "consignee",
    "consignee_contact_id",
    "customs_staff_id",
    "data_charge",
    "delivery_time",
    "document_cutoff_time",
    "booked_weight",
    "density",
    "quotation",
    "include_tc",
    "warehouse_data_remark",
    "notify_pickup",
    "pickup_time",
    "internal_remark",
    "customer_remark",
    "air_freight_cost",
    "other_charge",
    "payment_date",
}


class PrebookingService:
    def __init__(self, db: Session):
        self.db = db
        self.warehouse_files = WarehouseFileService(db)

    def base_query(self) -> Select[tuple[WaybillPrebooking]]:
        return select(WaybillPrebooking).options(
            selectinload(WaybillPrebooking.carrier_agent),
            selectinload(WaybillPrebooking.consignee_contact),
            selectinload(WaybillPrebooking.customs_staff),
            selectinload(WaybillPrebooking.converted_waybill),
        )

    def list(
        self,
        current_user: User,
        *,
        page: int,
        page_size: int,
        status: str | None = None,
    ) -> tuple[list[WaybillPrebookingOut], int, int, int]:
        PermissionService.assert_waybill_write(current_user)
        pagination = normalize_pagination(page, page_size)
        query = self.base_query()
        if status:
            query = query.where(WaybillPrebooking.status == status)
        query = query.order_by(
            (WaybillPrebooking.status != "draft").asc(),
            WaybillPrebooking.planned_flight_date.asc(),
            WaybillPrebooking.id.desc(),
        )
        total = int(self.db.scalar(select(func.count()).select_from(query.order_by(None).subquery())) or 0)
        items = list(self.db.scalars(query.offset(pagination.offset).limit(pagination.page_size)))
        return [self.to_out(item) for item in items], total, pagination.page, pagination.page_size

    def get(self, prebooking_id: int, current_user: User) -> WaybillPrebooking:
        PermissionService.assert_waybill_write(current_user)
        prebooking = self.db.scalar(self.base_query().where(WaybillPrebooking.id == prebooking_id))
        if prebooking is None:
            raise not_found("Prebooking not found")
        return prebooking

    def create(self, payload: WaybillPrebookingCreate, current_user: User) -> WaybillPrebooking:
        PermissionService.assert_waybill_write(current_user)
        agent = self._get_agent(payload.carrier_agent_id)
        data = payload.model_dump(exclude={"carrier_agent_id"}, exclude_none=True)
        prebooking = WaybillPrebooking(
            **data,
            carrier_agent_id=agent.id,
            agent=agent.agent_name,
            include_tc=payload.include_tc if payload.include_tc is not None else False,
            notify_pickup=payload.notify_pickup if payload.notify_pickup is not None else False,
            status="draft",
            created_by=current_user.id,
            updated_by=current_user.id,
        )
        self.db.add(prebooking)
        self.db.commit()
        return self.get(prebooking.id, current_user)

    def update(self, prebooking_id: int, payload: WaybillPrebookingUpdate, current_user: User) -> WaybillPrebooking:
        prebooking = self.get(prebooking_id, current_user)
        if prebooking.status == "converted":
            raise bad_request("prebooking_already_converted")
        data = payload.model_dump(exclude_unset=True)
        if "status" in data and data["status"] not in {"draft", "cancelled"}:
            raise bad_request("invalid_prebooking_status")
        if "carrier_agent_id" in data and data["carrier_agent_id"] is not None:
            agent = self._get_agent(data.pop("carrier_agent_id"))
            prebooking.carrier_agent_id = agent.id
            prebooking.agent = agent.agent_name
        for key, value in data.items():
            if key in PREBOOKING_FIELDS or key == "status":
                setattr(prebooking, key, value)
        prebooking.updated_by = current_user.id
        self.db.commit()
        return self.get(prebooking.id, current_user)

    def convert(self, prebooking_id: int, payload: WaybillCreate, current_user: User):
        prebooking = self.get(prebooking_id, current_user)
        if prebooking.status != "draft":
            raise bad_request("prebooking_not_convertible")
        merged = self._merge_convert_payload(prebooking, payload)
        self._validate_convert_payload(merged)
        waybill = WaybillService(self.db).create(WaybillCreate(**merged), current_user)

        receipts = list(
            self.db.scalars(select(WarehouseReceipt).where(WarehouseReceipt.prebooking_id == prebooking.id))
        )
        for receipt in receipts:
            receipt.prebooking_id = None
            receipt.waybill_id = waybill.id
            for box in self.warehouse_files.boxes.list_by_receipt_id(receipt.id):
                box.current_waybill_id = waybill.id
                box.status = "bound"
                box.never_bound_direct_upload = False
                box.unbound_reason = None
                box.unbound_remark = None
        if receipts:
            waybill.warehouse_no = receipts[-1].warehouse_no
        prebooking.status = "converted"
        prebooking.converted_waybill_id = waybill.id
        prebooking.updated_by = current_user.id
        waybill.updated_by = current_user.id
        self.db.commit()
        return WaybillService(self.db).get_visible(waybill.id, current_user)

    def to_out(self, prebooking: WaybillPrebooking) -> WaybillPrebookingOut:
        receipts = list(
            self.db.scalars(
                select(WarehouseReceipt)
                .where(WarehouseReceipt.prebooking_id == prebooking.id)
                .order_by(WarehouseReceipt.updated_at.desc(), WarehouseReceipt.id.desc())
            )
        )
        return WaybillPrebookingOut(
            id=prebooking.id,
            status=prebooking.status,
            carrier_agent_id=prebooking.carrier_agent_id,
            carrier_agent=prebooking.carrier_agent,
            agent=prebooking.agent,
            planned_flight_date=prebooking.planned_flight_date,
            booked_volume=prebooking.booked_volume,
            waybill_no=prebooking.waybill_no,
            departure_port=prebooking.departure_port,
            destination_port=prebooking.destination_port,
            planned_flight_no=prebooking.planned_flight_no,
            planned_route_text=prebooking.planned_route_text,
            consignee=prebooking.consignee,
            consignee_contact_id=prebooking.consignee_contact_id,
            consignee_contact=prebooking.consignee_contact,
            customs_staff_id=prebooking.customs_staff_id,
            customs_staff=prebooking.customs_staff,
            data_charge=prebooking.data_charge,
            delivery_time=prebooking.delivery_time,
            document_cutoff_time=prebooking.document_cutoff_time,
            booked_weight=prebooking.booked_weight,
            density=prebooking.density,
            quotation=prebooking.quotation,
            include_tc=prebooking.include_tc,
            warehouse_data_remark=prebooking.warehouse_data_remark,
            notify_pickup=prebooking.notify_pickup,
            pickup_time=prebooking.pickup_time,
            internal_remark=prebooking.internal_remark,
            customer_remark=prebooking.customer_remark,
            air_freight_cost=prebooking.air_freight_cost,
            other_charge=prebooking.other_charge,
            payment_date=prebooking.payment_date,
            converted_waybill_id=prebooking.converted_waybill_id,
            converted_waybill=prebooking.converted_waybill,
            receipts=[self.warehouse_files.get_receipt_summary(receipt.id) for receipt in receipts],
            created_at=prebooking.created_at,
            updated_at=prebooking.updated_at,
        )

    def _get_agent(self, carrier_agent_id: int) -> CarrierAgent:
        agent = self.db.get(CarrierAgent, carrier_agent_id)
        if agent is None:
            raise bad_request("carrier_agent_not_found")
        if not agent.enabled:
            raise bad_request("carrier_agent_disabled")
        return agent

    def _merge_convert_payload(self, prebooking: WaybillPrebooking, payload: WaybillCreate) -> dict:
        data = payload.model_dump(exclude_unset=True)
        defaults = {
            "carrier_agent_id": prebooking.carrier_agent_id,
            "booked_volume": prebooking.booked_volume,
            "planned_flight_date": prebooking.planned_flight_date,
            "waybill_no": prebooking.waybill_no,
            "departure_port": prebooking.departure_port,
            "destination_port": prebooking.destination_port,
            "planned_flight_no": prebooking.planned_flight_no,
            "planned_route_text": prebooking.planned_route_text,
            "consignee": prebooking.consignee,
            "consignee_contact_id": prebooking.consignee_contact_id,
            "customs_staff_id": prebooking.customs_staff_id,
            "data_charge": prebooking.data_charge,
            "delivery_time": prebooking.delivery_time,
            "document_cutoff_time": prebooking.document_cutoff_time,
            "booked_weight": prebooking.booked_weight,
            "density": prebooking.density,
            "quotation": prebooking.quotation,
            "include_tc": prebooking.include_tc,
            "warehouse_data_remark": prebooking.warehouse_data_remark,
            "notify_pickup": prebooking.notify_pickup,
            "pickup_time": prebooking.pickup_time,
            "internal_remark": prebooking.internal_remark,
            "customer_remark": prebooking.customer_remark,
            "air_freight_cost": prebooking.air_freight_cost,
            "other_charge": prebooking.other_charge,
            "payment_date": prebooking.payment_date,
        }
        for key, value in defaults.items():
            if data.get(key) in (None, "") and value is not None:
                data[key] = value
        return data

    def _validate_convert_payload(self, data: dict) -> None:
        required = {
            "waybill_no": "waybill_no_required",
            "carrier_agent_id": "carrier_agent_required",
            "departure_port": "departure_port_required",
            "destination_port": "destination_port_required",
            "planned_route_text": "planned_route_required",
            "booked_weight": "booked_weight_required",
            "booked_volume": "booked_volume_required",
            "quotation": "quotation_required",
        }
        missing = [code for key, code in required.items() if data.get(key) in (None, "")]
        has_flight_info = bool(data.get("planned_flight_info"))
        has_flight_parts = bool(data.get("planned_flight_no")) and isinstance(data.get("planned_flight_date"), date)
        if not has_flight_info and not has_flight_parts:
            missing.append("planned_flight_required")
        if missing:
            raise bad_request(",".join(missing))
