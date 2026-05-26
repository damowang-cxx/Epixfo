from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date


PLANNED_FLIGHT_INFO_PATTERN = re.compile(r"^\s*([A-Za-z0-9]+)\s*[/_]\s*(\d{1,2})\s*$")


@dataclass(frozen=True)
class ParsedPlannedFlightInfo:
    flight_no: str
    flight_date: date


@dataclass(frozen=True)
class PlannedFlightFilter:
    flight_no: str
    flight_date: date | None = None


def parse_planned_flight_info(value: str, *, today: date) -> ParsedPlannedFlightInfo:
    match = PLANNED_FLIGHT_INFO_PATTERN.match(value or "")
    if not match:
        raise ValueError("planned_flight_info_format")

    flight_no = match.group(1).strip().upper()
    if not flight_no:
        raise ValueError("planned_flight_no_required")

    day = int(match.group(2))
    if day <= 0:
        raise ValueError("planned_flight_day_invalid")

    current_month = _safe_date(today.year, today.month, day)
    if current_month is not None and current_month >= today:
        return ParsedPlannedFlightInfo(flight_no=flight_no, flight_date=current_month)

    next_year, next_month = _next_month(today.year, today.month)
    next_month_date = _safe_date(next_year, next_month, day)
    if next_month_date is not None:
        return ParsedPlannedFlightInfo(flight_no=flight_no, flight_date=next_month_date)

    raise ValueError("planned_flight_day_invalid")


def extract_planned_flight_no(value: str | None) -> str | None:
    cleaned = (value or "").strip()
    if not cleaned:
        return None
    match = PLANNED_FLIGHT_INFO_PATTERN.match(cleaned)
    if match:
        return match.group(1).strip().upper()
    return cleaned.upper()


def parse_planned_flight_filter(value: str, *, today: date) -> PlannedFlightFilter:
    cleaned = (value or "").strip()
    if not cleaned:
        raise ValueError("planned_flight_no_required")
    match = PLANNED_FLIGHT_INFO_PATTERN.match(cleaned)
    if match:
        parsed = parse_planned_flight_info(cleaned, today=today)
        return PlannedFlightFilter(flight_no=parsed.flight_no, flight_date=parsed.flight_date)
    return PlannedFlightFilter(flight_no=cleaned.upper())


def _next_month(year: int, month: int) -> tuple[int, int]:
    if month == 12:
        return year + 1, 1
    return year, month + 1


def _safe_date(year: int, month: int, day: int) -> date | None:
    try:
        return date(year, month, day)
    except ValueError:
        return None
