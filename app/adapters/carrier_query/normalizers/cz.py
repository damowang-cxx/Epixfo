"""把南方航空 spider（`csair.client.query_awb`）的原生 dict
翻译成 [app.parsers.cz_parser.CZParser](../../../parsers/cz_parser.py) 期待的统一形态 dict。

输入示例（来自 tang）：
    {
        "awbNo": "784-83707805",
        "awbType": "international",
        "queriedAt": "2026-05-19T16:23:34+08:00",
        "awbInfo":   {"awbNo", "carrier", "route", "commodity", "totalPieces", "totalWeightKg", "totalVolume"},
        "booking":   [{"bookingNo", "route", "fromStation", "toStation", "flight", "flightDate",
                       "pieces", "weight", "volume", "bookingType"}, ...],
        "cargoState": [{"time", "city", "flight", "status", "pieces", "weight"}, ...],
        "combine":    [{"time", "city", "status", "pieces", "weight"}, ...],
        "milestones": {"received": {"status", "src"}, ...},
        "errorInfo": null,
    }

输出（CZParser 期待）：
    {
        "waybill_info":   {"official_waybill_no", "carrier_text", "route_text", "goods_name",
                           "total_pieces", "total_weight", "total_volume"},
        "booking_info":   [{"booking_no", "route_text", "departure_airport", "arrival_airport",
                            "flight_no", "flight_date", "pieces", "weight", "volume", "booking_type"}, ...],
        "status_events":  [{"event_time", "event_city", "flight_no", "status_text",
                            "pieces", "weight"}, ...],
        "assembly_events":[{"event_time", "event_city", "status_text", "pieces", "weight"}, ...],
        # 备份层（不被 Parser 消费）：
        "csair": {"awbNo", "awbType", "queriedAt", "milestones", "errorInfo"},
    }
"""

from __future__ import annotations

from typing import Any


class CZNormalizer:
    adapter_code = "cz_adapter"

    def normalize(self, raw: dict[str, Any]) -> dict[str, Any]:
        return {
            "waybill_info": _normalize_awb_info(raw.get("awbInfo")),
            "booking_info": [_normalize_booking(row) for row in (raw.get("booking") or [])],
            "status_events": [_normalize_cargo_state(row) for row in (raw.get("cargoState") or [])],
            "assembly_events": [_normalize_combine(row) for row in (raw.get("combine") or [])],
            "csair": {
                "awbNo": raw.get("awbNo"),
                "awbType": raw.get("awbType"),
                "queriedAt": raw.get("queriedAt"),
                "milestones": raw.get("milestones"),
                "errorInfo": raw.get("errorInfo"),
            },
        }


def _normalize_awb_info(info: dict[str, Any] | None) -> dict[str, Any] | None:
    if not info:
        return None
    return {
        "official_waybill_no": info.get("awbNo"),
        "carrier_text": info.get("carrier"),
        "route_text": info.get("route"),
        "goods_name": info.get("commodity"),
        "total_pieces": info.get("totalPieces"),
        "total_weight": info.get("totalWeightKg"),
        "total_volume": info.get("totalVolume"),
    }


def _normalize_booking(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "booking_no": row.get("bookingNo"),
        "route_text": row.get("route"),
        "departure_airport": row.get("fromStation"),
        "arrival_airport": row.get("toStation"),
        "flight_no": row.get("flight"),
        "flight_date": row.get("flightDate"),
        "pieces": row.get("pieces"),
        "weight": row.get("weight"),
        "volume": row.get("volume"),
        "booking_type": row.get("bookingType"),
        # 来自航班动态查询（active_flight.py）的精确时间，已为 ISO 字符串或 None
        "departure_planned_time": row.get("depPlanTime"),
        "departure_actual_time": row.get("depActualTime"),
        "arrival_planned_time": row.get("arrPlanTime"),
        "arrival_actual_time": row.get("arrActualTime"),
    }


def _normalize_cargo_state(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "event_time": row.get("time"),
        "event_city": row.get("city"),
        "flight_no": row.get("flight"),
        "status_text": row.get("status"),
        "pieces": row.get("pieces"),
        "weight": row.get("weight"),
    }


def _normalize_combine(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "event_time": row.get("time"),
        "event_city": row.get("city"),
        "status_text": row.get("status"),
        "pieces": row.get("pieces"),
        "weight": row.get("weight"),
    }
