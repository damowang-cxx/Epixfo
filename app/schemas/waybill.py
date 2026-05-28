from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import AlertLevel, CarrierQueryMethod, OfficialEventType, QueryStatus, WaybillLifecycleStatus
from app.schemas.board import BoardSummaryOut
from app.schemas.carrier import CarrierAgentOut
from app.schemas.consignee import ConsigneeContactOut
from app.schemas.user import UserSummaryOut


class WaybillPlanIn(BaseModel):
    planned_flight_info: str | None = Field(default=None, max_length=64)
    planned_flight_no: str | None = Field(default=None, max_length=32)
    planned_flight_date: date | None = None
    planned_destination: str | None = Field(default=None, max_length=16)
    planned_route_text: str | None = Field(default=None, max_length=255)


class WaybillBaseIn(BaseModel):
    departure_port: str | None = Field(default=None, max_length=16)
    destination_port: str | None = Field(default=None, max_length=16)
    carrier_agent_id: int | None = None
    warehouse_no: str | None = Field(default=None, max_length=128)
    outbound_date: date | None = None
    consignee: str | None = Field(default=None, max_length=255)
    consignee_contact_id: int | None = None
    document_operator_id: int | None = None
    route_staff_id: int | None = None
    customs_staff_id: int | None = None
    data_charge: Decimal | None = None
    delivery_time: datetime | None = None
    document_cutoff_time: datetime | None = None
    booked_weight: Decimal | None = None
    booked_volume: Decimal | None = None
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


class WaybillCreate(WaybillBaseIn, WaybillPlanIn):
    waybill_no: str = Field(max_length=64)


class WaybillUpdate(WaybillBaseIn, WaybillPlanIn):
    pass


class ManualStatusRequest(BaseModel):
    lifecycle_status: WaybillLifecycleStatus


class WaybillAccessRequest(BaseModel):
    waybill_no: str = Field(max_length=64)


class WaybillStatusCount(BaseModel):
    status: WaybillLifecycleStatus
    count: int


class WaybillBulkImportCreated(BaseModel):
    id: int
    waybill_no: str


class WaybillBulkImportError(BaseModel):
    row_number: int
    waybill_no: str | None = None
    message: str


class WaybillBulkImportResult(BaseModel):
    file_name: str
    created_count: int
    skipped_count: int
    errors: list[WaybillBulkImportError]
    created_waybills: list[WaybillBulkImportCreated]


class WaybillBulkUpdateRequest(BaseModel):
    waybill_ids: list[int] = Field(min_length=1)
    field: str = Field(max_length=64)
    value: Any = None

    @field_validator("waybill_ids")
    @classmethod
    def unique_waybill_ids(cls, value: list[int]) -> list[int]:
        seen: set[int] = set()
        unique: list[int] = []
        for item in value:
            if item in seen:
                continue
            seen.add(item)
            unique.append(item)
        return unique


class WaybillBulkUpdateItem(BaseModel):
    id: int
    waybill_no: str


class WaybillBulkUpdateError(BaseModel):
    id: int
    waybill_no: str | None = None
    message: str


class WaybillBulkUpdateResult(BaseModel):
    success_count: int
    failed_count: int
    updated_waybills: list[WaybillBulkUpdateItem]
    errors: list[WaybillBulkUpdateError]


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
    departure_port: str | None = None
    destination_port: str | None = None
    agent: str | None = None
    carrier_agent_id: int | None = None
    carrier_agent: CarrierAgentOut | None = None
    warehouse_no: str | None = None
    outbound_date: date | None = None
    consignee: str | None = None
    consignee_contact_id: int | None = None
    consignee_contact: ConsigneeContactOut | None = None
    board_id: int | None = None
    board: BoardSummaryOut | None = None
    document_operator_id: int | None = None
    route_staff_id: int | None = None
    customs_staff_id: int | None = None
    customs_staff: UserSummaryOut | None = None
    customs_data_uploaded_at: datetime | None = None
    customs_data_uploaded_by: int | None = None
    customs_data_uploaded_by_user: UserSummaryOut | None = None
    data_charge: Decimal | None = None
    delivery_time: datetime | None = None
    document_cutoff_time: datetime | None = None
    booked_weight: Decimal | None = None
    booked_volume: Decimal | None = None
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
    lifecycle_status: WaybillLifecycleStatus
    alert_level: AlertLevel | None = None
    monitor_enabled: bool
    first_monitor_at: datetime | None = None
    last_query_at: datetime | None = None
    next_query_at: datetime | None = None
    consecutive_query_failures: int
    plan: WaybillPlanOut | None = None
    official_estimated_flight_date: date | None = None
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
