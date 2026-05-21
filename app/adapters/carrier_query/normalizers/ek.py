from __future__ import annotations

from typing import Any


class EKNormalizer:
    adapter_code = "ek_adapter"

    def normalize(self, raw: dict[str, Any]) -> dict[str, Any]:
        orders = raw.get("orders") or []
        primary = orders[0] if orders else {}

        return {
            "waybill_info": _normalize_waybill_info(primary),
            "booking_info": _normalize_bookings(orders),
            "status_events": _normalize_status_events(orders),
            "assembly_events": [],
            "emirates": {
                "awb": raw.get("awb"),
                "fetchedAt": raw.get("fetchedAt"),
                "found": raw.get("found"),
                "totalCount": raw.get("totalCount"),
                "cache": raw.get("cache"),
                "raw": raw.get("raw"),
            },
        }


def _normalize_waybill_info(order: dict[str, Any]) -> dict[str, Any] | None:
    if not order:
        return None
    document = order.get("document") or {}
    route = order.get("route") or {}
    cargo = order.get("cargo") or {}
    quantity = _first(cargo.get("quantityInfo") or [])
    return {
        "official_waybill_no": document.get("formatted"),
        "carrier_text": "EK / Emirates SkyCargo",
        "route_text": _route_text(
            _location_code(route.get("origin")),
            _location_code(route.get("destination")),
        ),
        "goods_name": cargo.get("goodsDescription"),
        "total_pieces": quantity.get("piece") if isinstance(quantity, dict) else None,
        "total_weight": _value(quantity, "weight") if isinstance(quantity, dict) else None,
        "total_volume": _value(quantity, "volume") if isinstance(quantity, dict) else None,
        "raw_data": {
            "document": document,
            "route": route,
            "cargo": cargo,
            "orderStatus": order.get("orderStatus"),
        },
    }


def _normalize_bookings(orders: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[tuple[Any, ...]] = set()
    for order in orders:
        booking_no = order.get("bookingReferenceNumber")
        for index, leg in enumerate(order.get("itinerary") or [], start=1):
            transport = leg.get("transportInfo") or {}
            departure = _location_code(leg.get("boardPoint")) or transport.get("origin")
            arrival = _location_code(leg.get("offPoint")) or transport.get("destination")
            flight_no = _flight_no(transport)
            flight_date = _date_part(transport.get("date") or _get_path(leg, "departureDateTimeLocal.schedule"))
            identity = (booking_no, index, flight_no, flight_date, departure, arrival)
            if identity in seen:
                continue
            seen.add(identity)
            quantity = leg.get("quantity") or {}
            rows.append(
                {
                    "booking_no": booking_no,
                    "route_text": _route_text(departure, arrival),
                    "segment_order": index,
                    "departure_airport": departure,
                    "arrival_airport": arrival,
                    "flight_no": flight_no,
                    "flight_date": flight_date,
                    "pieces": quantity.get("piece"),
                    "weight": _value(quantity, "weight"),
                    "volume": _value(quantity, "volume"),
                    "booking_type": order.get("orderSource") or _get_path(order, "orderStatus.description"),
                    "departure_planned_time": _get_path(leg, "departureDateTimeLocal.schedule"),
                    "departure_actual_time": _get_path(leg, "departureDateTimeLocal.actual"),
                    "arrival_planned_time": _get_path(leg, "arrivalDateTimeLocal.schedule"),
                    "arrival_actual_time": _get_path(leg, "arrivalDateTimeLocal.actual"),
                    "raw_data": leg,
                }
            )
    return rows


def _normalize_status_events(orders: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[tuple[Any, ...]] = set()
    for order in orders:
        for milestone in order.get("milestones") or []:
            row = _normalize_milestone(milestone)
            identity = (
                row.get("event_time"),
                row.get("event_city"),
                row.get("flight_no"),
                row.get("status_text"),
                row.get("pieces"),
                row.get("weight"),
            )
            if identity in seen:
                continue
            seen.add(identity)
            rows.append(row)

        for customs in _customs_rows(order):
            row = _normalize_customs(customs)
            identity = (
                row.get("event_time"),
                row.get("event_city"),
                row.get("flight_no"),
                row.get("status_text"),
                row.get("pieces"),
                row.get("weight"),
            )
            if identity in seen:
                continue
            seen.add(identity)
            rows.append(row)

    return sorted(rows, key=lambda item: item.get("event_time") or "")


def _normalize_milestone(row: dict[str, Any]) -> dict[str, Any]:
    status_data = row.get("statusData") or {}
    itinerary = status_data.get("itinerary") or {}
    transport = itinerary.get("transportInfo") or {}
    quantity = status_data.get("quantity") or {}
    return {
        "event_time": row.get("achieved"),
        "event_city": _location_code(row.get("station")),
        "flight_no": _flight_no(transport),
        "status_text": row.get("description") or row.get("code") or "",
        "normalized_event_type": _normalize_event_type(row.get("code"), row.get("description")),
        "pieces": quantity.get("piece"),
        "weight": _value(quantity, "weight"),
        "raw_data": row,
    }


def _normalize_customs(row: dict[str, Any]) -> dict[str, Any]:
    transport = row.get("transportInfo") or {}
    action_status = row.get("actionStatus") or {}
    status_description = action_status.get("description") or action_status.get("code") or "Customs status"
    return {
        "event_time": row.get("statusDate"),
        "event_city": _location_code(row.get("airport")) or transport.get("origin") or transport.get("destination"),
        "flight_no": _flight_no(transport),
        "status_text": f"Customs: {status_description}",
        "normalized_event_type": "unknown",
        "pieces": row.get("piece"),
        "weight": _value(row, "weight"),
        "raw_data": row,
    }


def _customs_rows(order: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    cargo = order.get("cargo") or {}
    rows.extend(_as_list(_get_path(cargo, "customsInformation.customsReferenceInfo")))
    for item in order.get("orderItems") or []:
        item_cargo = item.get("cargo") or {}
        rows.extend(_as_list(_get_path(item_cargo, "customsInformation.customsReferenceInfo")))
    return [row for row in rows if isinstance(row, dict)]


def _normalize_event_type(code: Any, description: Any) -> str:
    code_text = str(code or "").upper()
    text = str(description or "").lower()
    if code_text in {"NFD"} or "notified" in text:
        return "pickup_notified"
    if code_text in {"DLV"} or any(token in text for token in ("delivered", "collected", "picked up")):
        return "picked_up"
    if code_text in {"ARR"} or "arrived" in text:
        return "flight_arrived"
    if code_text in {"DEP"} or "departed" in text:
        return "flight_departed"
    if code_text in {"MAN"} or "manifested" in text or "booked" in text:
        return "cargo_loaded"
    if code_text in {"RCF", "RCS", "REC"} or "received" in text:
        return "cargo_received"
    return "unknown"


def _flight_no(transport: dict[str, Any]) -> str | None:
    carrier = str(transport.get("carrier") or "").strip()
    number = str(transport.get("number") or "").strip()
    extension = str(transport.get("extensionNumber") or "").strip()
    if not number:
        return None
    return f"{carrier}{number}{extension}" if carrier else f"{number}{extension}"


def _route_text(departure: str | None, arrival: str | None) -> str | None:
    if departure and arrival:
        return f"{departure}-{arrival}"
    return departure or arrival


def _location_code(value: Any) -> str | None:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return value.get("code")
    return None


def _value(value: dict[str, Any], key: str) -> Any:
    nested = value.get(key)
    if isinstance(nested, dict):
        return nested.get("value")
    return None


def _date_part(value: Any) -> str | None:
    if value in (None, ""):
        return None
    return str(value).strip()[:10]


def _first(items: list[Any]) -> Any:
    return items[0] if items else {}


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _get_path(value: Any, path_expression: str) -> Any:
    current = value
    for key in path_expression.split("."):
        if current is None:
            return None
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current
