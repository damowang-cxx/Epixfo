from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import WaybillLifecycleStatus


class BoardSummaryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    board_no: str
    actual_board_no: str | None = None
    consignee_contact_id: int | None = None
    consignee_text: str | None = None
    booked_volume: Decimal | None = None
    booked_weight: Decimal | None = None
    member_count: int = 0
    total_booked_volume: Decimal = Decimal("0.000")
    total_booked_weight: Decimal = Decimal("0.000")


class BoardWaybillOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    waybill_no: str
    consignee_contact_id: int | None = None
    consignee: str | None = None
    booked_volume: Decimal | None = None
    lifecycle_status: WaybillLifecycleStatus


class BoardOut(BoardSummaryOut):
    waybills: list[BoardWaybillOut] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class BoardCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    actual_board_no: str | None = Field(default=None, max_length=128)
    waybill_nos: list[str] = Field(min_length=1)


class BoardUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    actual_board_no: str | None = Field(default=None, max_length=128)


class BoardWaybillBindRequest(BaseModel):
    waybill_nos: list[str] = Field(min_length=1)


class BoardBindError(BaseModel):
    waybill_no: str
    message: str
