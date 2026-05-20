"""验证 [CZNormalizer](app/adapters/carrier_query/normalizers/cz.py) 把 spider 输出
里的 4 个航班动态时间字段透传到 CZParser 期待的标准 key，并能被 [CZParser](app/parsers/cz_parser.py)
正确解析为 datetime。
"""

from __future__ import annotations

from datetime import datetime

from app.adapters.carrier_query.normalizers.cz import CZNormalizer
from app.parsers.cz_parser import CZParser


def _sample_raw() -> dict:
    return {
        "awbInfo": {
            "awbNo": "784-83707805",
            "carrier": "CZ/CZ",
            "route": "广州(CAN)--阿姆斯特丹(AMS)",
            "commodity": "GENERAL",
            "totalPieces": "50",
            "totalWeightKg": "1041",
            "totalVolume": "4.03",
        },
        "booking": [
            {
                "bookingNo": "63151182",
                "route": "CAN-AMS",
                "fromStation": "CAN",
                "toStation": "AMS",
                "flight": "CZ307",
                "flightDate": "2026-05-20",
                "pieces": "50",
                "weight": "1041",
                "volume": "4.03",
                "bookingType": "KK",
                # spider 写入的 4 个 ISO 字符串字段
                "depPlanTime": "2026-05-20 00:20:00",
                "depActualTime": "2026-05-20 00:26:00",
                "arrPlanTime": "2026-05-20 05:35:00",
                "arrActualTime": "2026-05-20 05:47:00",
            }
        ],
        "cargoState": [],
        "combine": [],
        "milestones": {},
        "errorInfo": None,
    }


def test_normalizer_passes_through_active_flight_times() -> None:
    normalized = CZNormalizer().normalize(_sample_raw())
    booking = normalized["booking_info"][0]
    assert booking["departure_planned_time"] == "2026-05-20 00:20:00"
    assert booking["departure_actual_time"] == "2026-05-20 00:26:00"
    assert booking["arrival_planned_time"] == "2026-05-20 05:35:00"
    assert booking["arrival_actual_time"] == "2026-05-20 05:47:00"


def test_normalizer_keeps_none_when_spider_omits_times() -> None:
    raw = _sample_raw()
    raw["booking"][0].pop("depActualTime")
    raw["booking"][0]["arrActualTime"] = None
    normalized = CZNormalizer().normalize(raw)
    booking = normalized["booking_info"][0]
    assert booking["departure_actual_time"] is None
    assert booking["arrival_actual_time"] is None
    # 计划时间仍然在
    assert booking["departure_planned_time"] == "2026-05-20 00:20:00"


def test_cz_parser_promotes_times_to_datetime() -> None:
    """端到端：normalizer 输出 -> CZParser 解析 -> ParsedOfficialFlightSegment 4 字段是 datetime。"""
    normalized = CZNormalizer().normalize(_sample_raw())
    parsed = CZParser().parse(normalized)
    segment = parsed.flight_segments[0]
    assert segment.departure_planned_time == datetime(2026, 5, 20, 0, 20, 0)
    assert segment.departure_actual_time == datetime(2026, 5, 20, 0, 26, 0)
    assert segment.arrival_planned_time == datetime(2026, 5, 20, 5, 35, 0)
    assert segment.arrival_actual_time == datetime(2026, 5, 20, 5, 47, 0)


def test_cz_parser_handles_missing_active_flight_times() -> None:
    """老 booking 没有这 4 字段时，parser 不应当抛错，4 字段就是 None。"""
    raw = _sample_raw()
    for k in ("depPlanTime", "depActualTime", "arrPlanTime", "arrActualTime"):
        raw["booking"][0].pop(k, None)
    normalized = CZNormalizer().normalize(raw)
    parsed = CZParser().parse(normalized)
    segment = parsed.flight_segments[0]
    assert segment.departure_planned_time is None
    assert segment.departure_actual_time is None
    assert segment.arrival_planned_time is None
    assert segment.arrival_actual_time is None
