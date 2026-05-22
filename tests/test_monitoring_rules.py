from datetime import date, datetime, timedelta

from app.models.enums import WaybillLifecycleStatus
from app.utils.datetime_utils import app_timezone, compute_monitor_window, compute_next_query_at


def test_monitor_window_starts_three_days_before_flight_date() -> None:
    first_monitor_at, next_query_at = compute_monitor_window(date(2026, 5, 12))

    assert first_monitor_at.date() == date(2026, 5, 9)
    assert next_query_at == first_monitor_at


def test_picked_up_stops_future_queries() -> None:
    next_query_at = compute_next_query_at(date(2026, 5, 12), WaybillLifecycleStatus.PICKED_UP)

    assert next_query_at is None


def test_active_monitoring_runs_every_two_hours_after_monitor_window_starts() -> None:
    now = datetime(2026, 5, 9, 8, 30, tzinfo=app_timezone())
    next_query_at = compute_next_query_at(date(2026, 5, 12), WaybillLifecycleStatus.MONITORING, now=now)

    assert next_query_at == now + timedelta(hours=2)
