from __future__ import annotations

import logging

from app.core.platform_patch import patch_platform_wmi

patch_platform_wmi()

from sqlalchemy.orm import Session

from app.adapters.carrier_query.base import CarrierQueryResult
from app.adapters.carrier_query.registry import registry
from app.models.enums import QueryStatus
from app.parsers.base import ParsedCarrierData
from app.parsers.registry import parser_registry
from app.repositories.carrier_repository import CarrierRepository
from app.schemas.lookup import (
    LookupAssemblyEvent,
    LookupFlightSegment,
    LookupOfficialInfo,
    LookupStatusEvent,
    WaybillLookupResponse,
)
from app.utils.waybill_utils import (
    carrier_prefix_from_waybill,
    normalize_waybill_no,
    validate_waybill_no,
)

logger = logging.getLogger("epixfo.service.lookup")


class WaybillLookupService:
    """Ad-hoc 运单官网查询：纯函数链路，不做任何 DB 写入。

    流程：校验 → prefix 路由 → adapter.query → parser.parse → 转 Pydantic。
    """

    def __init__(self, db: Session) -> None:
        self.db = db
        self.carriers = CarrierRepository(db)

    async def lookup(self, raw_waybill_no: str) -> WaybillLookupResponse:
        if not validate_waybill_no(raw_waybill_no):
            return WaybillLookupResponse(
                waybill_no=raw_waybill_no,
                status=QueryStatus.FAILED,
                error_code="invalid_waybill_no",
                error_message=f"运单号格式无效：{raw_waybill_no!r}",
            )

        waybill_no = normalize_waybill_no(raw_waybill_no)
        prefix = carrier_prefix_from_waybill(waybill_no)

        mapping = self.carriers.get_mapping_by_prefix(prefix)
        if mapping is None:
            return WaybillLookupResponse(
                waybill_no=waybill_no,
                status=QueryStatus.FAILED,
                error_code="carrier_prefix_unmapped",
                error_message=f"前缀 {prefix} 未在承运人映射表中配置",
            )

        adapter = registry.get(mapping.adapter_code)
        if adapter is None:
            return WaybillLookupResponse(
                waybill_no=waybill_no,
                status=QueryStatus.FAILED,
                carrier_code=mapping.carrier_code,
                adapter_code=mapping.adapter_code,
                error_code="adapter_not_found",
                error_message=f"adapter_code={mapping.adapter_code!r} 未在 registry 中注册",
            )

        logger.info("ad-hoc lookup %s via %s", waybill_no, mapping.adapter_code)
        result = await adapter.query(waybill_no)

        if result.status != QueryStatus.SUCCESS or result.raw_response is None:
            return _from_failed_result(waybill_no, result)

        parser = parser_registry.get(mapping.adapter_code)
        parsed = parser.parse(result.raw_response) if parser is not None else ParsedCarrierData()

        return _from_parsed(waybill_no, result, parsed)


def _from_failed_result(waybill_no: str, result: CarrierQueryResult) -> WaybillLookupResponse:
    return WaybillLookupResponse(
        waybill_no=waybill_no,
        status=result.status,
        carrier_code=result.carrier_code,
        adapter_code=result.adapter_code,
        query_method=result.query_method,
        error_code=result.error_code,
        error_message=result.error_message,
        raw_response=result.raw_response,
    )


def _from_parsed(
    waybill_no: str,
    result: CarrierQueryResult,
    parsed: ParsedCarrierData,
) -> WaybillLookupResponse:
    official_info = None
    if parsed.official_info is not None:
        info = parsed.official_info
        official_info = LookupOfficialInfo(
            official_waybill_no=info.official_waybill_no,
            carrier_text=info.carrier_text,
            route_text=info.route_text,
            goods_name=info.goods_name,
            total_pieces=info.total_pieces,
            total_weight=info.total_weight,
            total_volume=info.total_volume,
        )

    return WaybillLookupResponse(
        waybill_no=waybill_no,
        status=result.status,
        carrier_code=result.carrier_code,
        adapter_code=result.adapter_code,
        query_method=result.query_method,
        official_info=official_info,
        flight_segments=[
            LookupFlightSegment(
                booking_no=seg.booking_no,
                route_text=seg.route_text,
                departure_airport=seg.departure_airport,
                arrival_airport=seg.arrival_airport,
                flight_no=seg.flight_no,
                flight_date=seg.flight_date,
                pieces=seg.pieces,
                weight=seg.weight,
                volume=seg.volume,
                booking_type=seg.booking_type,
            )
            for seg in parsed.flight_segments
        ],
        status_events=[
            LookupStatusEvent(
                event_time_local=event.event_time_local,
                event_time_text=event.event_time_text,
                event_city=event.event_city,
                flight_no=event.flight_no,
                status_text=event.status_text,
                normalized_event_type=event.normalized_event_type,
                pieces=event.pieces,
                weight=event.weight,
            )
            for event in parsed.status_events
        ],
        assembly_events=[
            LookupAssemblyEvent(
                event_time_local=event.event_time_local,
                event_time_text=event.event_time_text,
                event_city=event.event_city,
                status_text=event.status_text,
                uld_no=event.uld_no,
                pieces=event.pieces,
                weight=event.weight,
            )
            for event in parsed.assembly_events
        ],
        raw_response=result.raw_response,
    )
