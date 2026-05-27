from __future__ import annotations

from datetime import date, datetime

from app.core.platform_patch import patch_platform_wmi

patch_platform_wmi()

from sqlalchemy import Select, case, func, select
from sqlalchemy.orm import Session, aliased, selectinload

from app.models import (
    AirWaybill,
    WaybillBoard,
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
                selectinload(AirWaybill.board).selectinload(WaybillBoard.waybills),
                selectinload(AirWaybill.customs_staff),
                selectinload(AirWaybill.customs_data_uploaded_by_user),
            )
            .outerjoin(WaybillBoard, WaybillBoard.id == AirWaybill.board_id)
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
        return list(self.db.scalars(self._apply_management_order(query).offset(skip).limit(limit)))

    def count_filtered(self, query: Select[tuple[AirWaybill]]) -> int:
        count_query = select(func.count()).select_from(query.order_by(None).subquery())
        return int(self.db.scalar(count_query) or 0)

    def _apply_management_order(self, query: Select[tuple[AirWaybill]]) -> Select[tuple[AirWaybill]]:
        sort_plan = aliased(WaybillPlan)
        board_waybill = aliased(AirWaybill)
        board_plan = aliased(WaybillPlan)
        board_dates = (
            select(
                board_waybill.board_id.label("board_id"),
                func.min(board_plan.planned_flight_date).label("min_planned_flight_date"),
                func.max(board_plan.planned_flight_date).label("max_planned_flight_date"),
            )
            .outerjoin(board_plan, board_plan.waybill_id == board_waybill.id)
            .where(board_waybill.board_id.is_not(None))
            .group_by(board_waybill.board_id)
            .subquery()
        )

        completed_statuses = [WaybillLifecycleStatus.PICKED_UP, WaybillLifecycleStatus.VOIDED]
        is_completed = AirWaybill.lifecycle_status.in_(completed_statuses)
        active_sort_date = func.coalesce(board_dates.c.min_planned_flight_date, sort_plan.planned_flight_date)
        completed_sort_date = func.coalesce(board_dates.c.max_planned_flight_date, sort_plan.planned_flight_date)

        return (
            query.order_by(None)
            .outerjoin(sort_plan, sort_plan.waybill_id == AirWaybill.id)
            .outerjoin(board_dates, board_dates.c.board_id == AirWaybill.board_id)
            .order_by(
                case((is_completed, 1), else_=0).asc(),
                case((is_completed, 0), (active_sort_date.is_(None), 1), else_=0).asc(),
                case((is_completed, None), else_=active_sort_date).asc(),
                case((is_completed & completed_sort_date.is_(None), 1), else_=0).asc(),
                case((is_completed, completed_sort_date), else_=None).desc(),
                WaybillBoard.board_no.is_(None).asc(),
                WaybillBoard.board_no.asc(),
                AirWaybill.id.desc(),
            )
        )

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
                            WaybillLifecycleStatus.VOIDED,
                        ]
                    ),
                )
                .order_by(AirWaybill.next_query_at.asc(), AirWaybill.id.asc())
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
