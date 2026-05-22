from __future__ import annotations

from datetime import date, datetime

from app.core.platform_patch import patch_platform_wmi

patch_platform_wmi()

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session, selectinload

from app.models import (
    AirWaybill,
    WaybillAlert,
    WaybillAssemblyEvent,
    WaybillOfficialFlightSegment,
    WaybillOfficialInfo,
    WaybillPlan,
    WaybillQuerySnapshot,
    WaybillStatusEvent,
)
from app.models.enums import AlertLevel, WaybillLifecycleStatus


class WaybillRepository:
    def __init__(self, db: Session):
        self.db = db

    def base_query(self) -> Select[tuple[AirWaybill]]:
        return (
            select(AirWaybill)
            .options(
                selectinload(AirWaybill.plan),
                selectinload(AirWaybill.official_flight_segments),
            )
            .order_by(AirWaybill.id.desc())
        )

    def get(self, waybill_id: int) -> AirWaybill | None:
        return self.db.scalar(self.base_query().where(AirWaybill.id == waybill_id))

    def get_by_no(self, waybill_no: str) -> AirWaybill | None:
        return self.db.scalar(select(AirWaybill).where(AirWaybill.waybill_no == waybill_no))

    def list_filtered(
        self,
        query: Select[tuple[AirWaybill]],
        skip: int,
        limit: int,
    ) -> list[AirWaybill]:
        return list(self.db.scalars(query.offset(skip).limit(limit)))

    def count_filtered(self, query: Select[tuple[AirWaybill]]) -> int:
        count_query = select(func.count()).select_from(query.order_by(None).subquery())
        return int(self.db.scalar(count_query) or 0)

    def count_by_status(self, query: Select[tuple[AirWaybill]]) -> dict[WaybillLifecycleStatus, int]:
        """对已应用权限/筛选的 query 做 group_by(lifecycle_status) 计数。

        借助 subquery 的方式保留传入 query 的 join + where 条件，再在外层 group_by。
        """
        sub = query.order_by(None).subquery()
        stmt = select(sub.c.lifecycle_status, func.count()).group_by(sub.c.lifecycle_status)
        rows = self.db.execute(stmt).all()
        return {row[0]: int(row[1]) for row in rows}

    def apply_filters(
        self,
        query: Select[tuple[AirWaybill]],
        waybill_no: str | None = None,
        carrier_code: str | None = None,
        destination_port: str | None = None,
        planned_flight_no: str | None = None,
        planned_flight_date_from: date | None = None,
        planned_flight_date_to: date | None = None,
        lifecycle_status: WaybillLifecycleStatus | None = None,
        alert_level: AlertLevel | None = None,
        created_at_from: datetime | None = None,
        created_at_to: datetime | None = None,
    ) -> Select[tuple[AirWaybill]]:
        if planned_flight_no or planned_flight_date_from or planned_flight_date_to:
            query = query.join(WaybillPlan)
        if waybill_no:
            query = query.where(AirWaybill.waybill_no.ilike(f"%{waybill_no}%"))
        if carrier_code:
            query = query.where(AirWaybill.carrier_code == carrier_code)
        if destination_port:
            query = query.where(AirWaybill.destination_port == destination_port)
        if planned_flight_no:
            query = query.where(WaybillPlan.planned_flight_no == planned_flight_no)
        if planned_flight_date_from:
            query = query.where(WaybillPlan.planned_flight_date >= planned_flight_date_from)
        if planned_flight_date_to:
            query = query.where(WaybillPlan.planned_flight_date <= planned_flight_date_to)
        if lifecycle_status:
            query = query.where(AirWaybill.lifecycle_status == lifecycle_status)
        if alert_level:
            query = query.where(AirWaybill.alert_level == alert_level)
        if created_at_from:
            query = query.where(AirWaybill.created_at >= created_at_from)
        if created_at_to:
            query = query.where(AirWaybill.created_at <= created_at_to)
        return query

    def due_waybills(self, now: datetime, limit: int = 50) -> list[AirWaybill]:
        return list(
            self.db.scalars(
                self.base_query()
                .where(
                    AirWaybill.monitor_enabled.is_(True),
                    AirWaybill.next_query_at <= now,
                    AirWaybill.lifecycle_status.notin_(
                        [
                            WaybillLifecycleStatus.PICKED_UP,
                            WaybillLifecycleStatus.CLOSED,
                            WaybillLifecycleStatus.VOIDED,
                        ]
                    ),
                )
                .limit(limit)
            )
        )

    def replace_official_info(self, waybill_id: int, official_info: WaybillOfficialInfo) -> None:
        self.db.query(WaybillOfficialInfo).filter(WaybillOfficialInfo.waybill_id == waybill_id).delete()
        self.db.add(official_info)

    def replace_segments(self, waybill_id: int, segments: list[WaybillOfficialFlightSegment]) -> None:
        self.db.query(WaybillOfficialFlightSegment).filter(WaybillOfficialFlightSegment.waybill_id == waybill_id).delete()
        self.db.add_all(segments)

    def status_events(self, waybill_id: int) -> list[WaybillStatusEvent]:
        return list(
            self.db.scalars(
                select(WaybillStatusEvent)
                .where(WaybillStatusEvent.waybill_id == waybill_id)
                .order_by(WaybillStatusEvent.event_time_local)
            )
        )

    def add_status_events(self, events: list[WaybillStatusEvent]) -> None:
        for event in events:
            exists = self.db.scalar(
                select(WaybillStatusEvent.id).where(
                    WaybillStatusEvent.waybill_id == event.waybill_id,
                    WaybillStatusEvent.event_hash == event.event_hash,
                )
            )
            if not exists:
                self.db.add(event)

    def add_assembly_events(self, events: list[WaybillAssemblyEvent]) -> None:
        for event in events:
            exists = self.db.scalar(
                select(WaybillAssemblyEvent.id).where(
                    WaybillAssemblyEvent.waybill_id == event.waybill_id,
                    WaybillAssemblyEvent.event_hash == event.event_hash,
                )
            )
            if not exists:
                self.db.add(event)

    def official_info(self, waybill_id: int) -> WaybillOfficialInfo | None:
        return self.db.scalar(select(WaybillOfficialInfo).where(WaybillOfficialInfo.waybill_id == waybill_id))

    def official_segments(self, waybill_id: int) -> list[WaybillOfficialFlightSegment]:
        return list(
            self.db.scalars(
                select(WaybillOfficialFlightSegment)
                .where(WaybillOfficialFlightSegment.waybill_id == waybill_id)
                .order_by(WaybillOfficialFlightSegment.segment_order)
            )
        )

    def assembly_events(self, waybill_id: int) -> list[WaybillAssemblyEvent]:
        return list(self.db.scalars(select(WaybillAssemblyEvent).where(WaybillAssemblyEvent.waybill_id == waybill_id)))

    def query_snapshots(self, waybill_id: int) -> list[WaybillQuerySnapshot]:
        return list(
            self.db.scalars(
                select(WaybillQuerySnapshot)
                .where(WaybillQuerySnapshot.waybill_id == waybill_id)
                .order_by(WaybillQuerySnapshot.queried_at.desc())
            )
        )

    def alerts(self, waybill_id: int) -> list[WaybillAlert]:
        return list(self.db.scalars(select(WaybillAlert).where(WaybillAlert.waybill_id == waybill_id)))
