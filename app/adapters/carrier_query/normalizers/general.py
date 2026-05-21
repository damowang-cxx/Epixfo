from __future__ import annotations

from typing import Any


class GeneralNormalizer:
    adapter_code = "general_adapter"

    def normalize(self, raw: dict[str, Any]) -> dict[str, Any]:
        orders = raw.get("orders") or []
        primary = orders[0] if orders else {}
        return {
            "waybill_info": _normalize_waybill_info(raw, primary),
            "booking_info": _normalize_bookings(orders),
            "status_events": _normalize_status_events(orders),
            "assembly_events": [],
            "general": {
                "source": raw.get("source"),
                "carrier": raw.get("carrier"),
                "awb": raw.get("awb"),
                "formattedAwb": raw.get("formattedAwb"),
                "found": raw.get("found"),
                "fetchedAt": raw.get("fetchedAt"),
                "totalCount": raw.get("totalCount"),
                "cache": raw.get("cache"),
                "raw": raw.get("raw"),
            },
        }


def _normalize_waybill_info(raw: dict[str, Any], order: dict[str, Any]) -> dict[str, Any] | None:
    if not order:
        return None
    route = order.get("route") or {}
    cargo = order.get("cargo") or {}
    airline = order.get("airline") or {}
    origin = _station_code(route.get("origin"))
    destination = _station_code(route.get("destination"))
    return {
        "official_waybill_no": _clean(order.get("formattedAwb") or raw.get("formattedAwb")),
        "carrier_text": _clean(raw.get("carrier") or airline.get("name")),
        "route_text": _route_text(origin, destination),
        "goods_name": None,
        "total_pieces": _clean(cargo.get("pieces")),
        "total_weight": _clean(cargo.get("weight")),
        "total_volume": _clean(cargo.get("volume")),
        "raw_data": {
            "status": order.get("status"),
            "route": route,
            "cargo": cargo,
            "airline": airline,
        },
    }


def _normalize_bookings(orders: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[tuple[Any, ...]] = set()
    for order in orders:
        cargo = order.get("cargo") or {}
        status = order.get("status") or {}
        for index, flight in enumerate(order.get("flights") or [], start=1):
            departure = _airport_code(flight.get("departStation"))
            arrival = _airport_code(flight.get("arrivalStation"))
            flight_no = _flight_no(flight.get("flightNumber"))
            planned_depart = _clean(flight.get("plannedDepartTime"))
            actual_depart = _clean(flight.get("departTime"))
            planned_arrival = _clean(flight.get("plannedArrivalTime"))
            actual_arrival = _clean(flight.get("arrivalTime"))
            identity = (
                flight_no,
                departure,
                arrival,
                planned_depart,
                actual_depart,
                planned_arrival,
                actual_arrival,
            )
            if identity in seen:
                continue
            seen.add(identity)
            rows.append(
                {
                    "booking_no": None,
                    "route_text": _route_text(departure, arrival),
                    "segment_order": index,
                    "departure_airport": departure,
                    "arrival_airport": arrival,
                    "flight_no": flight_no,
                    "flight_date": _date_part(planned_depart or actual_depart),
                    "pieces": _clean(flight.get("pieces")) or _clean(cargo.get("pieces")),
                    "weight": _clean(flight.get("weight")) or _clean(cargo.get("weight")),
                    "volume": _clean(cargo.get("volume")),
                    "booking_type": _clean(flight.get("status") or status.get("code")),
                    "departure_planned_time": planned_depart,
                    "departure_actual_time": actual_depart,
                    "arrival_planned_time": planned_arrival,
                    "arrival_actual_time": actual_arrival,
                    "raw_data": flight,
                }
            )
    return rows


def _normalize_status_events(orders: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[tuple[Any, ...]] = set()
    for order in orders:
        for event in order.get("events") or []:
            event_time = _clean(event.get("time") or event.get("actualTime") or event.get("plannedTime"))
            station = _airport_code(event.get("station"))
            flight_no = _flight_no(event.get("flightNumber"))
            status_text = _status_text(event)
            row = {
                "event_time": event_time,
                "event_city": station,
                "airport_code": station,
                "flight_no": flight_no,
                "status_text": status_text,
                "normalized_event_type": _normalize_event_type(
                    event.get("status"),
                    event.get("substatus"),
                    event.get("checkpointStatus"),
                    status_text,
                ),
                "pieces": _clean(event.get("pieces")),
                "weight": _clean(event.get("weight")),
                "raw_data": event,
            }
            identity = (
                row["event_time"],
                row["event_city"],
                row["flight_no"],
                row["status_text"],
                row["pieces"],
                row["weight"],
            )
            if identity in seen:
                continue
            seen.add(identity)
            rows.append(row)
    return sorted(rows, key=lambda item: item.get("event_time") or "")


def _status_text(event: dict[str, Any]) -> str:
    for key in (
        "event",
        "substatusDescription",
        "checkpointStatusDescription",
        "substatus",
        "checkpointStatus",
        "status",
    ):
        value = _clean(event.get(key))
        if value is not None:
            return value
    return ""


def _normalize_event_type(*values: Any) -> str:
    tokens = {str(value or "").strip().upper() for value in values if value not in (None, "")}
    text = " ".join(tokens).lower()
    if tokens & {"DLV"} or "delivered" in text or "picked" in text:
        return "picked_up"
    if tokens & {"NFD"} or "pickupnotified" in text or "notified" in text:
        return "pickup_notified"
    if tokens & {"DEP"} or "departed" in text:
        return "flight_departed"
    if tokens & {"ARR"} or "arrived" in text:
        return "flight_arrived"
    if tokens & {"PRE", "MAN"} or "booked" in text or "manifest" in text:
        return "cargo_loaded"
    if tokens & {"RCF", "RCS", "REC"} or "received" in text:
        return "cargo_received"
    return "unknown"


def _station_code(value: Any) -> str | None:
    if isinstance(value, dict):
        return _airport_code(value.get("code"))
    return _airport_code(value)


def _airport_code(value: Any) -> str | None:
    text = _clean(value)
    if text is None:
        return None
    return text.upper()


def _flight_no(value: Any) -> str | None:
    text = _clean(value)
    if text is None:
        return None
    return "".join(text.split()).upper()


def _route_text(departure: str | None, arrival: str | None) -> str | None:
    if departure and arrival:
        return f"{departure}-{arrival}"
    return departure or arrival


def _date_part(value: Any) -> str | None:
    text = _clean(value)
    if text is None:
        return None
    return text[:10]


def _clean(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, str):
        text = value.strip()
        return text or None
    return value
