from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from app.models.enums import OfficialEventType
from app.parsers.base import (
    ParsedAssemblyEvent,
    ParsedCarrierData,
    ParsedOfficialFlightSegment,
    ParsedOfficialInfo,
    ParsedStatusEvent,
)


def _pick(row: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in row:
            return row[key]
    return None


def _int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    return int(Decimal(str(value)))


def _decimal(value: Any) -> Decimal | None:
    if value in (None, ""):
        return None
    return Decimal(str(value))


def _date(value: Any):
    if value in (None, ""):
        return None
    if hasattr(value, "year") and not isinstance(value, str):
        return value
    text = str(value).strip()
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(text[:19], fmt).date()
        except ValueError:
            continue
    return None


def _datetime(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value.replace(tzinfo=None)
    text = str(value).strip().replace("T", " ").replace("Z", "")
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S"):
        try:
            return datetime.strptime(text[:19], fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(str(value).strip()).replace(tzinfo=None)
    except ValueError:
        return None


def _event_type(value: Any) -> OfficialEventType:
    if isinstance(value, OfficialEventType):
        return value
    try:
        return OfficialEventType(str(value))
    except ValueError:
        return OfficialEventType.UNKNOWN


class GeneralParser:
    def parse(self, raw_response: dict[str, Any]) -> ParsedCarrierData:
        bookings = raw_response.get("booking_info") or []
        waybill_info = raw_response.get("waybill_info")
        status_events = raw_response.get("status_events") or []
        assembly_events = raw_response.get("assembly_events") or []

        segments: list[ParsedOfficialFlightSegment] = []
        origin_airport = None
        for index, row in enumerate(bookings, start=1):
            if index == 1:
                origin_airport = _pick(row, "departure_airport")
            segments.append(
                ParsedOfficialFlightSegment(
                    booking_no=_pick(row, "booking_no"),
                    route_text=_pick(row, "route_text"),
                    departure_airport=_pick(row, "departure_airport"),
                    arrival_airport=_pick(row, "arrival_airport"),
                    flight_no=_pick(row, "flight_no"),
                    flight_date=_date(_pick(row, "flight_date")),
                    pieces=_int(_pick(row, "pieces")),
                    weight=_decimal(_pick(row, "weight")),
                    volume=_decimal(_pick(row, "volume")),
                    booking_type=_pick(row, "booking_type"),
                    departure_planned_time=_datetime(_pick(row, "departure_planned_time")),
                    departure_actual_time=_datetime(_pick(row, "departure_actual_time")),
                    arrival_planned_time=_datetime(_pick(row, "arrival_planned_time")),
                    arrival_actual_time=_datetime(_pick(row, "arrival_actual_time")),
                    raw_data=row.get("raw_data") if isinstance(row.get("raw_data"), dict) else row,
                )
            )

        official_info = None
        if isinstance(waybill_info, dict):
            official_info = ParsedOfficialInfo(
                official_waybill_no=_pick(waybill_info, "official_waybill_no"),
                carrier_text=_pick(waybill_info, "carrier_text"),
                route_text=_pick(waybill_info, "route_text"),
                goods_name=_pick(waybill_info, "goods_name"),
                total_pieces=_int(_pick(waybill_info, "total_pieces")),
                total_weight=_decimal(_pick(waybill_info, "total_weight")),
                total_volume=_decimal(_pick(waybill_info, "total_volume")),
                raw_data=waybill_info.get("raw_data") if isinstance(waybill_info.get("raw_data"), dict) else waybill_info,
            )
            if origin_airport is None and official_info.route_text:
                origin_airport = official_info.route_text.split("-", 1)[0]

        parsed_statuses: list[ParsedStatusEvent] = []
        origin_received_marked = False
        for row in status_events:
            event_type = _event_type(_pick(row, "normalized_event_type"))
            event_city = _pick(row, "event_city")
            if event_type == OfficialEventType.CARGO_RECEIVED and not origin_received_marked:
                if origin_airport is None or event_city == origin_airport:
                    event_type = OfficialEventType.ORIGIN_CARGO_RECEIVED
                    origin_received_marked = True
            parsed_statuses.append(
                ParsedStatusEvent(
                    event_time_local=_datetime(_pick(row, "event_time")),
                    event_time_text=str(_pick(row, "event_time") or ""),
                    event_city=event_city,
                    airport_code=_pick(row, "airport_code") or event_city,
                    flight_no=_pick(row, "flight_no"),
                    status_text=str(_pick(row, "status_text") or ""),
                    normalized_event_type=event_type,
                    pieces=_int(_pick(row, "pieces")),
                    weight=_decimal(_pick(row, "weight")),
                    raw_data=row.get("raw_data") if isinstance(row.get("raw_data"), dict) else row,
                )
            )

        parsed_assemblies: list[ParsedAssemblyEvent] = []
        for row in assembly_events:
            parsed_assemblies.append(
                ParsedAssemblyEvent(
                    event_time_local=_datetime(_pick(row, "event_time")),
                    event_time_text=str(_pick(row, "event_time") or ""),
                    event_city=_pick(row, "event_city"),
                    status_text=str(_pick(row, "status_text") or ""),
                    uld_no=_pick(row, "uld_no"),
                    pieces=_int(_pick(row, "pieces")),
                    weight=_decimal(_pick(row, "weight")),
                    raw_data=row.get("raw_data") if isinstance(row.get("raw_data"), dict) else row,
                )
            )

        return ParsedCarrierData(
            official_info=official_info,
            flight_segments=segments,
            status_events=parsed_statuses,
            assembly_events=parsed_assemblies,
        )
