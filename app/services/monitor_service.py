from __future__ import annotations

from dataclasses import dataclass

from app.core.platform_patch import patch_platform_wmi

patch_platform_wmi()

from sqlalchemy.orm import Session

from app.adapters.carrier_query.base import CarrierQueryResult
from app.adapters.carrier_query.registry import GENERAL_ADAPTER_CODE, registry
from app.models import (
    AirWaybill,
    WaybillAssemblyEvent,
    WaybillOfficialFlightSegment,
    WaybillOfficialInfo,
    WaybillQuerySnapshot,
    WaybillStatusEvent,
)
from app.models.enums import AlertLevel, CarrierAdapterType, QueryStatus
from app.models.system import AutoFlightQuerySettings
from app.parsers.base import ParsedCarrierData
from app.parsers.registry import parser_registry
from app.repositories.carrier_repository import CarrierRepository
from app.repositories.waybill_repository import WaybillRepository
from app.services.alert_service import AlertService
from app.services.auto_flight_query_settings_service import AutoFlightQuerySettingsService
from app.services.lifecycle_service import LifecycleService
from app.utils.datetime_utils import compute_next_query_at, utc_now
from app.utils.waybill_utils import event_hash


@dataclass
class _QueryAttempt:
    snapshot: WaybillQuerySnapshot
    parsed: ParsedCarrierData | None = None
    usable: bool = False


class MonitorService:
    def __init__(self, db: Session):
        self.db = db
        self.waybills = WaybillRepository(db)
        self.carriers = CarrierRepository(db)
        self.alerts = AlertService(db)
        self.lifecycle = LifecycleService(db)
        self.auto_settings = AutoFlightQuerySettingsService(db)

    async def trigger_query(self, waybill: AirWaybill) -> WaybillQuerySnapshot:
        auto_settings = self._auto_settings()
        final_attempt = await self._run_query_plan(waybill, self._query_plan(waybill, auto_settings))

        if final_attempt.usable and final_attempt.parsed is not None:
            self.alerts.handle_query_success(waybill)
            try:
                self._persist_parsed(waybill, final_attempt.snapshot.id, final_attempt.parsed)
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
        self.db.refresh(final_attempt.snapshot)
        return final_attempt.snapshot

    def _auto_settings(self) -> AutoFlightQuerySettings:
        return self.auto_settings.get_model()

    def _primary_adapter_code(self, waybill: AirWaybill) -> str | None:
        if waybill.carrier_code and waybill.carrier_code != "UNKNOWN":
            mapping = self.carriers.get_mapping_by_prefix(waybill.carrier_prefix or "")
            if mapping and self._adapter_type(mapping.adapter_code) != CarrierAdapterType.GENERAL.value:
                return mapping.adapter_code
        return None

    def _query_plan(self, waybill: AirWaybill, auto_settings: AutoFlightQuerySettings) -> list[str]:
        primary_adapter_code = self._primary_adapter_code(waybill)
        if primary_adapter_code is None:
            return self._general_adapter_codes()

        codes = [primary_adapter_code]
        if auto_settings.fallback_enabled:
            codes.extend(code for code in self._general_adapter_codes() if code != primary_adapter_code)
        return codes

    async def _run_query_plan(self, waybill: AirWaybill, adapter_codes: list[str]) -> _QueryAttempt:
        final_attempt: _QueryAttempt | None = None
        for adapter_code in adapter_codes:
            final_attempt = await self._query_with_adapter(waybill, adapter_code)
            if final_attempt.usable:
                return final_attempt

        if final_attempt is not None:
            return final_attempt
        return self._record_adapter_not_found(
            waybill,
            adapter_code=None,
            error_code="general_adapter_pool_empty",
            error_message="No enabled general carrier adapters were available.",
        )

    def _general_adapter_codes(self) -> list[str]:
        if hasattr(self.carriers, "list_general_query_adapters"):
            items = self.carriers.list_general_query_adapters(enabled_only=True)
            return [item.adapter_code for item in items if registry.get(item.adapter_code) is not None]
        return [GENERAL_ADAPTER_CODE] if registry.get(GENERAL_ADAPTER_CODE) is not None else []

    def _adapter_type(self, adapter_code: str | None) -> str | None:
        if not adapter_code:
            return None
        if hasattr(self.carriers, "get_query_adapter"):
            item = self.carriers.get_query_adapter(adapter_code)
            if item is not None:
                return item.adapter_type
        if adapter_code == GENERAL_ADAPTER_CODE:
            return CarrierAdapterType.GENERAL.value
        return CarrierAdapterType.DEDICATED.value if registry.get(adapter_code) is not None else None

    async def _query_with_adapter(self, waybill: AirWaybill, adapter_code: str) -> _QueryAttempt:
        adapter = registry.get(adapter_code)
        if adapter is None:
            return self._record_adapter_not_found(
                waybill,
                adapter_code=adapter_code,
                error_code="adapter_not_found",
                error_message="Carrier adapter was not found.",
            )

        started_at = utc_now()
        try:
            result = await adapter.query(waybill.waybill_no)
        except Exception as exc:
            result = CarrierQueryResult(
                status=QueryStatus.FAILED,
                carrier_code=waybill.carrier_code or adapter.carrier_code,
                adapter_code=adapter_code,
                query_method=adapter.query_method,
                error_code="adapter_exception",
                error_message=str(exc),
            )
        adapter_type = self._adapter_type(result.adapter_code)
        if adapter_type == CarrierAdapterType.GENERAL.value and waybill.carrier_code:
            result.carrier_code = waybill.carrier_code

        snapshot = WaybillQuerySnapshot(
            waybill_id=waybill.id,
            carrier_code=result.carrier_code,
            adapter_code=result.adapter_code,
            adapter_type=adapter_type,
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

        parsed = self._parse_result(snapshot, result)
        return _QueryAttempt(snapshot=snapshot, parsed=parsed, usable=parsed is not None)

    def _record_adapter_not_found(
        self,
        waybill: AirWaybill,
        adapter_code: str | None,
        error_code: str,
        error_message: str,
    ) -> _QueryAttempt:
        started_at = utc_now()
        snapshot = WaybillQuerySnapshot(
            waybill_id=waybill.id,
            carrier_code=waybill.carrier_code,
            adapter_code=adapter_code,
            adapter_type=self._adapter_type(adapter_code),
            query_status=QueryStatus.FAILED,
            error_code=error_code,
            error_message=error_message,
            started_at=started_at,
            finished_at=utc_now(),
        )
        self.db.add(snapshot)
        self.db.flush()
        return _QueryAttempt(snapshot=snapshot)

    def _parse_result(self, snapshot: WaybillQuerySnapshot, result: CarrierQueryResult) -> ParsedCarrierData | None:
        if result.status not in {QueryStatus.SUCCESS, QueryStatus.PARTIAL_SUCCESS} or result.raw_response is None:
            return None
        try:
            parser = parser_registry.get(result.adapter_code)
            if parser is None:
                raise ValueError("Parser not found")
            parsed = parser.parse(result.raw_response)
        except Exception as exc:
            snapshot.query_status = QueryStatus.FAILED
            snapshot.error_code = "parse_failed"
            snapshot.error_message = str(exc)
            return None

        if not (parsed.official_info or parsed.flight_segments or parsed.status_events or parsed.assembly_events):
            snapshot.query_status = QueryStatus.FAILED
            snapshot.error_code = "empty_parsed_data"
            snapshot.error_message = "Official response did not contain usable parsed data."
            return None
        return parsed

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
                departure_planned_time=segment.departure_planned_time,
                departure_actual_time=segment.departure_actual_time,
                arrival_planned_time=segment.arrival_planned_time,
                arrival_actual_time=segment.arrival_actual_time,
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
        waybill.next_query_at = compute_next_query_at(
            planned_date,
            waybill.lifecycle_status,
            interval_hours=self._auto_settings().query_interval_hours,
        )

    async def run_due_waybills(self, limit: int | None = None) -> int:
        scan_limit = limit if limit is not None else self._auto_settings().scan_limit
        due = self.waybills.due_waybills(utc_now(), scan_limit)
        for waybill in due:
            await self.trigger_query(waybill)
        return len(due)
