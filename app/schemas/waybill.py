from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import AlertLevel, CarrierQueryMethod, OfficialEventType, QueryStatus, WaybillLifecycleStatus
from app.schemas.carrier import CarrierAgentOut


class WaybillPlanIn(BaseModel):
    planned_flight_no: str | None = Field(default=None, max_length=32)
    planned_flight_date: date | None = None
    planned_destination: str | None = Field(default=None, max_length=16)
    planned_route_text: str | None = Field(default=None, max_length=255)


class WaybillBaseIn(BaseModel):
    destination_port: str | None = Field(default=None, max_length=16)
    carrier_agent_id: int | None = None
    warehouse_no: str | None = Field(default=None, max_length=128)
    consignee: str | None = Field(default=None, max_length=255)
    document_operator_id: int | None = None
    route_staff_id: int | None = None
    data_charge: Decimal | None = None
    delivery_time: datetime | None = None
    document_cutoff_time: datetime | None = None
    booked_weight: Decimal | None = None
    booked_volume: Decimal | None = None
    density: Decimal | None = None
    quotation: Decimal | None = None
    include_tc: bool | None = None
    warehouse_data_remark: str | None = None
    notify_pickup: bool | None = None
    pickup_time: datetime | None = None
    internal_remark: str | None = None
    customer_remark: str | None = None
    air_freight_cost: Decimal | None = None
    payment_date: date | None = None


class WaybillCreate(WaybillBaseIn, WaybillPlanIn):
    waybill_no: str = Field(max_length=64)


class WaybillUpdate(WaybillBaseIn, WaybillPlanIn):
    pass


class ManualStatusRequest(BaseModel):
    lifecycle_status: WaybillLifecycleStatus


class WaybillPlanOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    planned_flight_no: str | None = None
    planned_flight_date: date | None = None
    planned_destination: str | None = None
    planned_route_text: str | None = None


class WaybillOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    waybill_no: str
    carrier_prefix: str | None = None
    carrier_code: str | None = None
    destination_port: str | None = None
    agent: str | None = None
    carrier_agent_id: int | None = None
    carrier_agent: CarrierAgentOut | None = None
    warehouse_no: str | None = None
    consignee: str | None = None
    document_operator_id: int | None = None
    route_staff_id: int | None = None
    data_charge: Decimal | None = None
    delivery_time: datetime | None = None
    document_cutoff_time: datetime | None = None
    booked_weight: Decimal | None = None
    booked_volume: Decimal | None = None
    density: Decimal | None = None
    quotation: Decimal | None = None
    include_tc: bool
    warehouse_data_remark: str | None = None
    notify_pickup: bool
    pickup_time: datetime | None = None
    internal_remark: str | None = None
    customer_remark: str | None = None
    air_freight_cost: Decimal | None = None
    payment_date: date | None = None
    lifecycle_status: WaybillLifecycleStatus
    alert_level: AlertLevel | None = None
    monitor_enabled: bool
    first_monitor_at: datetime | None = None
    last_query_at: datetime | None = None
    next_query_at: datetime | None = None
    consecutive_query_failures: int
    plan: WaybillPlanOut | None = None
    created_at: datetime
    updated_at: datetime


class WaybillOfficialInfoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    waybill_id: int
    official_waybill_no: str | None = None
    carrier_text: str | None = None
    route_text: str | None = None
    goods_name: str | None = None
    total_pieces: int | None = None
    total_weight: Decimal | None = None
    total_volume: Decimal | None = None
    raw_data: dict[str, Any]


class WaybillOfficialFlightSegmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    waybill_id: int
    booking_no: str | None = None
    route_text: str | None = None
    segment_order: int
    departure_airport: str | None = None
    arrival_airport: str | None = None
    flight_no: str | None = None
    flight_date: date | None = None
    pieces: int | None = None
    weight: Decimal | None = None
    volume: Decimal | None = None
    booking_type: str | None = None
    departure_planned_time: datetime | None = None
    departure_actual_time: datetime | None = None
    arrival_planned_time: datetime | None = None
    arrival_actual_time: datetime | None = None
    raw_data: dict[str, Any]


class WaybillStatusEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    waybill_id: int
    event_time_local: datetime | None = None
    event_time_text: str | None = None
    event_city: str | None = None
    airport_code: str | None = None
    flight_no: str | None = None
    status_text: str
    normalized_event_type: OfficialEventType
    pieces: int | None = None
    weight: Decimal | None = None
    raw_data: dict[str, Any]


class WaybillAssemblyEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    waybill_id: int
    event_time_local: datetime | None = None
    event_time_text: str | None = None
    event_city: str | None = None
    status_text: str
    uld_no: str | None = None
    pieces: int | None = None
    weight: Decimal | None = None
    raw_data: dict[str, Any]


class WaybillQuerySnapshotOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    waybill_id: int
    carrier_code: str | None = None
    adapter_code: str | None = None
    query_method: CarrierQueryMethod | None = None
    query_status: QueryStatus
    raw_response: dict[str, Any] | None = None
    raw_text: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    queried_at: datetime
