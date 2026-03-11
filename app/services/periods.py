from __future__ import annotations

import calendar
from datetime import date, timedelta


def month_key(year: int, month: int) -> str:
    validate_month(year, month)
    return f"{year}-{month:02d}"


def month_bounds(year: int, month: int) -> tuple[date, date]:
    validate_month(year, month)
    days_in_month = calendar.monthrange(year, month)[1]
    return date(year, month, 1), date(year, month, days_in_month)


def days_in_month(year: int, month: int) -> int:
    validate_month(year, month)
    return calendar.monthrange(year, month)[1]


def validate_month(year: int, month: int) -> None:
    if month < 1 or month > 12:
        raise ValueError("Invalid month")


def validate_month_day(year: int, month: int, day: int) -> date:
    validate_month(year, month)
    max_day = days_in_month(year, month)
    if day < 1 or day > max_day:
        raise ValueError("Invalid day for month")
    return date(year, month, day)


def validate_week(year: int, week_number: int) -> None:
    try:
        date.fromisocalendar(year, week_number, 1)
    except ValueError as exc:
        raise ValueError("Invalid ISO week") from exc


def week_bounds(year: int, week_number: int) -> tuple[date, date]:
    validate_week(year, week_number)
    start = date.fromisocalendar(year, week_number, 1)
    return start, start + timedelta(days=6)


def previous_week_reference(year: int, week_number: int) -> tuple[int, int]:
    validate_week(year, week_number)
    previous_date = date.fromisocalendar(year, week_number, 1) - timedelta(days=7)
    iso = previous_date.isocalendar()
    return iso.year, iso.week
