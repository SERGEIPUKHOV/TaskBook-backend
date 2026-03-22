from __future__ import annotations

from datetime import date

import pytest

from app.services.periods import (
    month_key,
    previous_week_reference,
    validate_month_day,
    validate_week,
    week_bounds,
)


@pytest.mark.unit
class TestMonthKey:
    @pytest.mark.parametrize(
        ("year", "month", "expected"),
        [
            (2026, 3, "2026-03"),
            (2026, 1, "2026-01"),
            (2026, 12, "2026-12"),
            (2025, 10, "2025-10"),
        ],
    )
    def test_formats_month_keys(self, year: int, month: int, expected: str):
        assert month_key(year, month) == expected


@pytest.mark.unit
class TestWeekBounds:
    def test_week_one_starts_on_monday(self):
        start, _ = week_bounds(2026, 1)
        assert start.weekday() == 0
        assert start == date(2025, 12, 29)

    def test_week_one_ends_on_sunday(self):
        _, end = week_bounds(2026, 1)
        assert end.weekday() == 6
        assert end == date(2026, 1, 4)

    def test_week_range_spans_seven_days(self):
        start, end = week_bounds(2026, 12)
        assert (end - start).days == 6


@pytest.mark.unit
class TestPreviousWeekReference:
    def test_crosses_year_boundary(self):
        assert previous_week_reference(2026, 1) == (2025, 52)

    def test_moves_back_one_week_inside_same_year(self):
        assert previous_week_reference(2026, 12) == (2026, 11)


@pytest.mark.unit
class TestValidation:
    def test_validate_month_day_returns_date_for_valid_input(self):
        assert validate_month_day(2026, 2, 28) == date(2026, 2, 28)

    @pytest.mark.parametrize(
        ("year", "month", "day"),
        [
            (2026, 2, 30),
            (2026, 0, 1),
            (2026, 13, 1),
            (2026, 4, 31),
        ],
    )
    def test_validate_month_day_rejects_invalid_dates(self, year: int, month: int, day: int):
        with pytest.raises(ValueError):
            validate_month_day(year, month, day)

    def test_validate_week_rejects_invalid_iso_week(self):
        with pytest.raises(ValueError):
            validate_week(2026, 54)
