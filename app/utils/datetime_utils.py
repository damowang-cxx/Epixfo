from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from app.core.config import settings
from app.models.enums import WaybillLifecycleStatus


def app_timezone() -> ZoneInfo:
    return ZoneInfo(settings.app_timezone)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def local_now() -> datetime:
    return utc_now().astimezone(app_timezone())


def local_day_start(value: date) -> datetime:
    return datetime.combine(value, time.min, tzinfo=app_timezone())


def compute_monitor_window(planned_flight_date: date | None) -> tuple[datetime | None, datetime | None]:
    if planned_flight_date is None:
        return None, None
    first_monitor_at = local_day_start(planned_flight_date - timedelta(days=3))
    return first_monitor_at, first_monitor_at


def compute_next_query_at(
    planned_flight_date: date | None,
    lifecycle_status: WaybillLifecycleStatus,
    now: datetime | None = None,
    interval_hours: int = 2,
) -> datetime | None:
    if planned_flight_date is None:
        return None
    if lifecycle_status in {
        WaybillLifecycleStatus.PICKED_UP,
        WaybillLifecycleStatus.VOIDED,
    }:
        return None
    current = now or local_now()
    if current.tzinfo is None:
        current = current.replace(tzinfo=app_timezone())
    first_monitor_at = local_day_start(planned_flight_date - timedelta(days=3))
    if current < first_monitor_at:
        return first_monitor_at
    return current + timedelta(hours=interval_hours)
