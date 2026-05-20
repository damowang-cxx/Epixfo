from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Protocol

from app.models.enums import OfficialEventType


@dataclass
class ParsedOfficialFlightSegment:
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
    raw_data: dict[str, Any] = field(default_factory=dict)


@dataclass
class ParsedOfficialInfo:
    official_waybill_no: str | None = None
    carrier_text: str | None = None
    route_text: str | None = None
    goods_name: str | None = None
    total_pieces: int | None = None
    total_weight: Decimal | None = None
    total_volume: Decimal | None = None
    raw_data: dict[str, Any] = field(default_factory=dict)


@dataclass
class ParsedStatusEvent:
    event_time_local: datetime | None = None
    event_time_text: str | None = None
    event_city: str | None = None
    airport_code: str | None = None
    flight_no: str | None = None
    status_text: str = ""
    normalized_event_type: OfficialEventType = OfficialEventType.UNKNOWN
    pieces: int | None = None
    weight: Decimal | None = None
    raw_data: dict[str, Any] = field(default_factory=dict)


@dataclass
class ParsedAssemblyEvent:
    event_time_local: datetime | None = None
    event_time_text: str | None = None
    event_city: str | None = None
    status_text: str = ""
    uld_no: str | None = None
    pieces: int | None = None
    weight: Decimal | None = None
    raw_data: dict[str, Any] = field(default_factory=dict)


@dataclass
class ParsedCarrierData:
    official_info: ParsedOfficialInfo | None = None
    flight_segments: list[ParsedOfficialFlightSegment] = field(default_factory=list)
    status_events: list[ParsedStatusEvent] = field(default_factory=list)
    assembly_events: list[ParsedAssemblyEvent] = field(default_factory=list)


class CarrierParser(Protocol):
    def parse(self, raw_response: dict[str, Any]) -> ParsedCarrierData:
        ...
