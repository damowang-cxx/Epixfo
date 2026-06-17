from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field

from app.models.enums import CarrierAdapterType, CarrierQueryMethod, OfficialEventType, QueryStatus


class WaybillLookupRequest(BaseModel):
    waybill_no: str = Field(min_length=11, max_length=12)
    adapter_code: str | None = Field(default=None, max_length=64)


class LookupOfficialInfo(BaseModel):
    official_waybill_no: str | None = None
    carrier_text: str | None = None
    route_text: str | None = None
    goods_name: str | None = None
    total_pieces: int | None = None
    total_weight: Decimal | None = None
    total_volume: Decimal | None = None


class LookupFlightSegment(BaseModel):
    booking_no: str | None = None
    route_text: str | None = None
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


class LookupStatusEvent(BaseModel):
    event_time_local: datetime | None = None
    event_time_text: str | None = None
    event_city: str | None = None
    flight_no: str | None = None
    status_text: str
    normalized_event_type: OfficialEventType
    pieces: int | None = None
    weight: Decimal | None = None


class LookupAssemblyEvent(BaseModel):
    event_time_local: datetime | None = None
    event_time_text: str | None = None
    event_city: str | None = None
    status_text: str
    uld_no: str | None = None
    pieces: int | None = None
    weight: Decimal | None = None


class WaybillLookupResponse(BaseModel):
    waybill_no: str
    status: QueryStatus
    carrier_code: str | None = None
    adapter_code: str | None = None
    adapter_type: CarrierAdapterType | None = None
    query_method: CarrierQueryMethod | None = None
    error_code: str | None = None
    error_message: str | None = None
    official_info: LookupOfficialInfo | None = None
    flight_segments: list[LookupFlightSegment] = Field(default_factory=list)
    status_events: list[LookupStatusEvent] = Field(default_factory=list)
    assembly_events: list[LookupAssemblyEvent] = Field(default_factory=list)
    raw_response: dict[str, Any] | None = None
