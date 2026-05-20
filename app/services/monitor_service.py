from __future__ import annotations

from app.core.platform_patch import patch_platform_wmi

patch_platform_wmi()

from sqlalchemy.orm import Session

from app.adapters.carrier_query.registry import registry
from app.models import (
    AirWaybill,
    WaybillAssemblyEvent,
    WaybillOfficialFlightSegment,
    WaybillOfficialInfo,
    WaybillQuerySnapshot,
    WaybillStatusEvent,
)
from app.models.enums import QueryStatus
from app.models.enums import AlertLevel
from app.parsers.registry import parser_registry
from app.repositories.carrier_repository import CarrierRepository
from app.repositories.waybill_repository import WaybillRepository
from app.services.alert_service import AlertService
from app.services.lifecycle_service import LifecycleService
from app.utils.datetime_utils import compute_next_query_at, utc_now
from app.utils.waybill_utils import event_hash


class MonitorService:
    def __init__(self, db: Session):
        self.db = db
        self.waybills = WaybillRepository(db)
        self.carriers = CarrierRepository(db)
        self.alerts = AlertService(db)
        self.lifecycle = LifecycleService(db)

    async def trigger_query(self, waybill: AirWaybill) -> WaybillQuerySnapshot:
        adapter_code = None
        if waybill.carrier_code and waybill.carrier_code != "UNKNOWN":
            mapping = self.carriers.get_mapping_by_prefix(waybill.carrier_prefix or "")
            adapter_code = mapping.adapter_code if mapping else None
        adapter = registry.get(adapter_code)
        started_at = utc_now()
        if adapter is None:
            snapshot = WaybillQuerySnapshot(
                waybill_id=waybill.id,
                carrier_code=waybill.carrier_code,
                adapter_code=adapter_code,
                query_status=QueryStatus.FAILED,
                error_code="adapter_not_found",
                error_message="Carrier adapter was not found.",
                started_at=started_at,
                finished_at=utc_now(),
            )
            self.db.add(snapshot)
            self.alerts.handle_query_failure(waybill)
            self._schedule_next(waybill)
            self.db.commit()
            self.db.refresh(snapshot)
            return snapshot

        result = await adapter.query(waybill.waybill_no)
        snapshot = WaybillQuerySnapshot(
            waybill_id=waybill.id,
            carrier_code=result.carrier_code,
            adapter_code=result.adapter_code,
            query_method=result.query_method,
            query_status=result.status,
            raw_response=result.raw_response,
            raw_text=result.raw_text,
            error_code=result.error_code,
            error_message=result.error_message,
            started_at=started_at,
            finished_at=utc_now(),
        )
        self.db.add(snapshot)
        self.db.flush()

        if result.status == QueryStatus.SUCCESS and result.raw_response is not None:
            self.alerts.handle_query_success(waybill)
            try:
                parser = parser_registry.get(result.adapter_code)
                if parser is None:
                    raise ValueError("Parser not found")
                parsed = parser.parse(result.raw_response)
                self._persist_parsed(waybill, snapshot.id, parsed)
                self.db.flush()
                self.lifecycle.update_waybill_lifecycle(waybill)
                self.alerts.check_after_parse(waybill)
            except Exception as exc:
                self.alerts.create_or_update_active(
                    waybill,
                    "parse_failed",
                    level=AlertLevel.WARNING,
                    title="官网数据解析失败",
                    description=str(exc),
                )
        else:
            self.alerts.handle_query_failure(waybill)

        self._schedule_next(waybill)
        self.db.commit()
        self.db.refresh(snapshot)
        return snapshot

    def _persist_parsed(self, waybill: AirWaybill, snapshot_id: int, parsed) -> None:
        if parsed.official_info:
            info = parsed.official_info
            self.waybills.replace_official_info(
                waybill.id,
                WaybillOfficialInfo(
                    waybill_id=waybill.id,
                    official_waybill_no=info.official_waybill_no,
                    carrier_text=info.carrier_text,
                    route_text=info.route_text,
                    goods_name=info.goods_name,
                    total_pieces=info.total_pieces,
                    total_weight=info.total_weight,
                    total_volume=info.total_volume,
                    raw_data=info.raw_data,
                    source_snapshot_id=snapshot_id,
                ),
            )
        segments = [
            WaybillOfficialFlightSegment(
                waybill_id=waybill.id,
                booking_no=segment.booking_no,
                route_text=segment.route_text,
                segment_order=index,
                departure_airport=segment.departure_airport,
                arrival_airport=segment.arrival_airport,
                flight_no=segment.flight_no,
                flight_date=segment.flight_date,
                pieces=segment.pieces,
                weight=segment.weight,
                volume=segment.volume,
                booking_type=segment.booking_type,
                raw_data=segment.raw_data,
                source_snapshot_id=snapshot_id,
            )
            for index, segment in enumerate(parsed.flight_segments, start=1)
        ]
        self.waybills.replace_segments(waybill.id, segments)

        self.waybills.add_status_events(
            [
                WaybillStatusEvent(
                    waybill_id=waybill.id,
                    event_time_local=event.event_time_local,
                    event_time_text=event.event_time_text,
                    event_city=event.event_city,
                    airport_code=event.airport_code,
                    flight_no=event.flight_no,
                    status_text=event.status_text,
                    normalized_event_type=event.normalized_event_type,
                    pieces=event.pieces,
                    weight=event.weight,
                    raw_data=event.raw_data,
                    source_snapshot_id=snapshot_id,
                    event_hash=event_hash(
                        waybill.waybill_no,
                        event.event_time_text,
                        event.event_city,
                        event.flight_no,
                        event.status_text,
                        event.pieces,
                        event.weight,
                    ),
                )
                for event in parsed.status_events
            ]
        )
        self.waybills.add_assembly_events(
            [
                WaybillAssemblyEvent(
                    waybill_id=waybill.id,
                    event_time_local=event.event_time_local,
                    event_time_text=event.event_time_text,
                    event_city=event.event_city,
                    status_text=event.status_text,
                    uld_no=event.uld_no,
                    pieces=event.pieces,
                    weight=event.weight,
                    raw_data=event.raw_data,
                    source_snapshot_id=snapshot_id,
                    event_hash=event_hash(
                        waybill.waybill_no,
                        event.event_time_text,
                        event.event_city,
                        event.status_text,
                        event.pieces,
                        event.weight,
                    ),
                )
                for event in parsed.assembly_events
            ]
        )

    def _schedule_next(self, waybill: AirWaybill) -> None:
        planned_date = waybill.plan.planned_flight_date if waybill.plan else None
        waybill.last_query_at = utc_now()
        waybill.next_query_at = compute_next_query_at(planned_date, waybill.lifecycle_status)

    async def run_due_waybills(self, limit: int = 50) -> int:
        due = self.waybills.due_waybills(utc_now(), limit)
        for waybill in due:
            await self.trigger_query(waybill)
        return len(due)
