from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal
from typing import Any

from app.parsers.base import (
    ParsedAssemblyEvent,
    ParsedCarrierData,
    ParsedOfficialFlightSegment,
    ParsedOfficialInfo,
    ParsedStatusEvent,
)
from app.parsers.status_normalizer import normalize_status
from app.models.enums import OfficialEventType


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
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y年%m月%d日"):
        try:
            return datetime.strptime(str(value).strip(), fmt).date()
        except ValueError:
            continue
    return None


def _datetime(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value
    text = str(value).strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S", "%Y年%m月%d日 %H:%M:%S"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def _uld_no(status_text: str) -> str | None:
    match = re.search(r"（([^）]+)）|\(([^)]+)\)", status_text)
    if not match:
        return None
    return match.group(1) or match.group(2)


class CZParser:
    def parse(self, raw_response: dict[str, Any]) -> ParsedCarrierData:
        bookings = raw_response.get("booking_info") or raw_response.get("订舱信息") or []
        waybill_info = raw_response.get("waybill_info") or raw_response.get("运单信息") or None
        status_events = raw_response.get("status_events") or raw_response.get("货物状态") or []
        assembly_events = raw_response.get("assembly_events") or raw_response.get("货物组装信息") or []

        segments: list[ParsedOfficialFlightSegment] = []
        origin_city = None
        for index, row in enumerate(bookings, start=1):
            if index == 1:
                origin_city = _pick(row, "出发站", "departure_airport")
            segments.append(
                ParsedOfficialFlightSegment(
                    booking_no=_pick(row, "订舱号", "booking_no"),
                    route_text=_pick(row, "订舱航程", "route_text"),
                    departure_airport=_pick(row, "出发站", "departure_airport"),
                    arrival_airport=_pick(row, "到达站", "arrival_airport"),
                    flight_no=_pick(row, "航班号", "flight_no"),
                    flight_date=_date(_pick(row, "航班日期", "flight_date")),
                    pieces=_int(_pick(row, "件数", "pieces")),
                    weight=_decimal(_pick(row, "重量", "weight")),
                    volume=_decimal(_pick(row, "体积", "volume")),
                    booking_type=_pick(row, "订舱性质", "booking_type"),
                    departure_planned_time=_datetime(_pick(row, "起飞计划时间", "departure_planned_time")),
                    departure_actual_time=_datetime(_pick(row, "起飞实际时间", "departure_actual_time")),
                    arrival_planned_time=_datetime(_pick(row, "到达计划时间", "arrival_planned_time")),
                    arrival_actual_time=_datetime(_pick(row, "到达实际时间", "arrival_actual_time")),
                    raw_data=row,
                )
            )

        info_row = waybill_info[0] if isinstance(waybill_info, list) and waybill_info else waybill_info
        official_info = None
        if isinstance(info_row, dict):
            official_info = ParsedOfficialInfo(
                official_waybill_no=_pick(info_row, "运单号", "official_waybill_no", "waybill_no"),
                carrier_text=_pick(info_row, "承运人", "carrier_text"),
                route_text=_pick(info_row, "航程", "route_text"),
                goods_name=_pick(info_row, "货物品名", "goods_name"),
                total_pieces=_int(_pick(info_row, "总件数", "total_pieces")),
                total_weight=_decimal(_pick(info_row, "总重量(KG)", "总重量", "total_weight")),
                total_volume=_decimal(_pick(info_row, "总体积", "total_volume")),
                raw_data=info_row,
            )

        parsed_statuses: list[ParsedStatusEvent] = []
        origin_received_marked = False
        for row in status_events:
            status_text = str(_pick(row, "货物状态", "status_text") or "")
            event_type = normalize_status(status_text, _pick(row, "操作城市", "event_city"), origin_city)
            if event_type == OfficialEventType.CARGO_RECEIVED and not origin_received_marked:
                event_type = OfficialEventType.ORIGIN_CARGO_RECEIVED
                origin_received_marked = True
            parsed_statuses.append(
                ParsedStatusEvent(
                    event_time_local=_datetime(_pick(row, "操作时间 (当地时间)", "操作时间 (当地时间)", "操作时间", "event_time")),
                    event_time_text=str(_pick(row, "操作时间 (当地时间)", "操作时间 (当地时间)", "操作时间", "event_time") or ""),
                    event_city=_pick(row, "操作城市", "event_city"),
                    flight_no=_pick(row, "航班号", "flight_no"),
                    status_text=status_text,
                    normalized_event_type=event_type,
                    pieces=_int(_pick(row, "件数", "pieces")),
                    weight=_decimal(_pick(row, "重量", "weight")),
                    raw_data=row,
                )
            )

        parsed_assemblies: list[ParsedAssemblyEvent] = []
        for row in assembly_events:
            status_text = str(_pick(row, "货物状态", "status_text") or "")
            parsed_assemblies.append(
                ParsedAssemblyEvent(
                    event_time_local=_datetime(_pick(row, "操作时间 当前时区", "操作时间 当前时区", "操作时间", "event_time")),
                    event_time_text=str(_pick(row, "操作时间 当前时区", "操作时间 当前时区", "操作时间", "event_time") or ""),
                    event_city=_pick(row, "操作城市", "event_city"),
                    status_text=status_text,
                    uld_no=_uld_no(status_text),
                    pieces=_int(_pick(row, "件数", "pieces")),
                    weight=_decimal(_pick(row, "重量", "weight")),
                    raw_data=row,
                )
            )

        return ParsedCarrierData(
            official_info=official_info,
            flight_segments=segments,
            status_events=parsed_statuses,
            assembly_events=parsed_assemblies,
        )
