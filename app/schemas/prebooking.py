from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.box import WarehouseReceiptListOut
from app.schemas.carrier import CarrierAgentOut
from app.schemas.consignee import ConsigneeContactOut
from app.schemas.user import UserSummaryOut
from app.schemas.waybill import WaybillCreate, WaybillOut


PrebookingStatus = Literal["draft", "converted", "cancelled"]


class WaybillPrebookingBase(BaseModel):
    carrier_agent_id: int
    planned_flight_date: date
    booked_volume: Decimal = Field(gt=0)
    waybill_no: str | None = Field(default=None, max_length=64)
    departure_port: str | None = Field(default=None, max_length=16)
    destination_port: str | None = Field(default=None, max_length=16)
    planned_flight_no: str | None = Field(default=None, max_length=32)
    planned_route_text: str | None = Field(default=None, max_length=255)
    consignee: str | None = Field(default=None, max_length=255)
    consignee_contact_id: int | None = None
    customs_staff_id: int | None = None
    data_charge: Decimal | None = None
    delivery_time: datetime | None = None
    document_cutoff_time: datetime | None = None
    booked_weight: Decimal | None = None
    density: Decimal | None = None
    quotation: str | None = Field(default=None, max_length=64)
    include_tc: bool | None = None
    warehouse_data_remark: str | None = None
    notify_pickup: bool | None = None
    pickup_time: datetime | None = None
    internal_remark: str | None = None
    customer_remark: str | None = None
    air_freight_cost: Decimal | None = None
    other_charge: Decimal | None = None
    payment_date: date | None = None


class WaybillPrebookingCreate(WaybillPrebookingBase):
    pass


class WaybillPrebookingUpdate(BaseModel):
    carrier_agent_id: int | None = None
    planned_flight_date: date | None = None
    booked_volume: Decimal | None = Field(default=None, gt=0)
    waybill_no: str | None = Field(default=None, max_length=64)
    departure_port: str | None = Field(default=None, max_length=16)
    destination_port: str | None = Field(default=None, max_length=16)
    planned_flight_no: str | None = Field(default=None, max_length=32)
    planned_route_text: str | None = Field(default=None, max_length=255)
    consignee: str | None = Field(default=None, max_length=255)
    consignee_contact_id: int | None = None
    customs_staff_id: int | None = None
    data_charge: Decimal | None = None
    delivery_time: datetime | None = None
    document_cutoff_time: datetime | None = None
    booked_weight: Decimal | None = None
    density: Decimal | None = None
    quotation: str | None = Field(default=None, max_length=64)
    include_tc: bool | None = None
    warehouse_data_remark: str | None = None
    notify_pickup: bool | None = None
    pickup_time: datetime | None = None
    internal_remark: str | None = None
    customer_remark: str | None = None
    air_freight_cost: Decimal | None = None
    other_charge: Decimal | None = None
    payment_date: date | None = None
    status: Literal["draft", "cancelled"] | None = None


class WaybillPrebookingConvert(WaybillCreate):
    pass


class WaybillPrebookingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: str
    carrier_agent_id: int
    carrier_agent: CarrierAgentOut | None = None
    agent: str | None = None
    planned_flight_date: date
    booked_volume: Decimal
    waybill_no: str | None = None
    departure_port: str | None = None
    destination_port: str | None = None
    planned_flight_no: str | None = None
    planned_route_text: str | None = None
    consignee: str | None = None
    consignee_contact_id: int | None = None
    consignee_contact: ConsigneeContactOut | None = None
    customs_staff_id: int | None = None
    customs_staff: UserSummaryOut | None = None
    data_charge: Decimal | None = None
    delivery_time: datetime | None = None
    document_cutoff_time: datetime | None = None
    booked_weight: Decimal | None = None
    density: Decimal | None = None
    quotation: str | None = None
    include_tc: bool
    warehouse_data_remark: str | None = None
    notify_pickup: bool
    pickup_time: datetime | None = None
    internal_remark: str | None = None
    customer_remark: str | None = None
    air_freight_cost: Decimal | None = None
    other_charge: Decimal | None = None
    payment_date: date | None = None
    converted_waybill_id: int | None = None
    converted_waybill: WaybillOut | None = None
    receipts: list[WarehouseReceiptListOut] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
