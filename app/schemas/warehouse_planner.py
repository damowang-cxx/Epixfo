from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from app.schemas.box import WarehouseReceiptListOut
from app.schemas.carrier import CarrierAgentOut
from app.schemas.user import UserSummaryOut


PlannerSourceType = Literal["waybill", "prebooking", "import_waybill", "import_prebooking"]
PlannerCommitMode = Literal["all_or_none", "success_only"]
PlannerChannel = Literal["AMS", "LHR"]


class WarehousePlannerRow(BaseModel):
    source_type: PlannerSourceType
    source_id: int
    planning_channel: PlannerChannel = "AMS"
    waybill_no: str | None = Field(default=None, max_length=64)
    carrier_agent_id: int | None = None
    planned_flight_no: str | None = Field(default=None, max_length=32)
    planned_flight_date: date | None = None
    outbound_date: date | None = None
    receipt_ids: list[int] = Field(default_factory=list)
    consignee_contact_id: int | None = None
    customs_staff_id: int | None = None
    board_group_id: str | None = Field(default=None, max_length=64)
    board_group_order: int | None = None
    board_booked_volume: Decimal | None = None
    board_booked_weight: Decimal | None = None
    booked_volume: Decimal | None = None
    booked_weight: Decimal | None = None
    density: Decimal | None = None
    quotation: str | None = Field(default=None, max_length=64)
    include_tc: bool | None = None
    departure_port: str | None = Field(default=None, max_length=16)
    destination_port: str | None = Field(default=None, max_length=16)
    planned_route_text: str | None = Field(default=None, max_length=255)
    internal_remark: str | None = None
    source_updated_at: datetime | None = None

    @field_validator("receipt_ids")
    @classmethod
    def unique_receipt_ids(cls, value: list[int]) -> list[int]:
        seen: set[int] = set()
        unique: list[int] = []
        for item in value:
            if item in seen:
                continue
            seen.add(item)
            unique.append(item)
        return unique


class WarehousePlannerDraftOut(BaseModel):
    rows: list[WarehousePlannerRow]
    updated_at: datetime | None = None


class WarehousePlannerDraftSave(BaseModel):
    rows: list[WarehousePlannerRow] = Field(default_factory=list)


class WarehousePlannerCandidate(BaseModel):
    source_type: PlannerSourceType
    source_id: int
    label: str
    waybill_no: str | None = None
    carrier_agent_id: int | None = None
    carrier_agent: CarrierAgentOut | None = None
    planned_flight_no: str | None = None
    planned_flight_date: date | None = None
    outbound_date: date | None = None
    receipts: list[WarehouseReceiptListOut] = Field(default_factory=list)
    customs_staff_id: int | None = None
    customs_staff: UserSummaryOut | None = None
    booked_volume: Decimal | None = None
    booked_weight: Decimal | None = None
    density: Decimal | None = None
    quotation: str | None = None
    include_tc: bool | None = None
    departure_port: str | None = None
    destination_port: str | None = None
    planned_route_text: str | None = None
    internal_remark: str | None = None
    lifecycle_status: str | None = None
    source_updated_at: datetime


class WarehousePlannerCandidatesOut(BaseModel):
    waybills: list[WarehousePlannerCandidate]
    prebookings: list[WarehousePlannerCandidate]
    unbound_receipts: list[WarehouseReceiptListOut]


class WarehousePlannerRowsRequest(BaseModel):
    rows: list[WarehousePlannerRow] = Field(default_factory=list)


class WarehousePlannerCommitRequest(WarehousePlannerRowsRequest):
    mode: PlannerCommitMode


class WarehousePlannerRowError(BaseModel):
    field: str | None = None
    message: str


class WarehousePlannerRowResult(BaseModel):
    source_type: PlannerSourceType
    source_id: int
    status: Literal["valid", "invalid", "committed", "failed"]
    waybill_id: int | None = None
    waybill_no: str | None = None
    errors: list[WarehousePlannerRowError] = Field(default_factory=list)


class WarehousePlannerValidateResult(BaseModel):
    valid_count: int
    invalid_count: int
    results: list[WarehousePlannerRowResult]


class WarehousePlannerCommitResult(BaseModel):
    success_count: int
    failed_count: int
    results: list[WarehousePlannerRowResult]
    remaining_rows: list[WarehousePlannerRow] = Field(default_factory=list)
    skipped_due_to_all_or_none: bool = False


class WarehousePlannerBulkImportWarning(BaseModel):
    row_number: int
    field: str
    raw_value: str | None = None
    message: str


class WarehousePlannerBulkImportError(BaseModel):
    row_number: int | None = None
    waybill_no: str | None = None
    message: str


class WarehousePlannerBulkImportResult(BaseModel):
    file_name: str
    imported_count: int
    skipped_count: int
    rows: list[WarehousePlannerRow] = Field(default_factory=list)
    warnings: list[WarehousePlannerBulkImportWarning] = Field(default_factory=list)
    errors: list[WarehousePlannerBulkImportError] = Field(default_factory=list)


def model_to_jsonable(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, list):
        return [model_to_jsonable(item) for item in value]
    return value
