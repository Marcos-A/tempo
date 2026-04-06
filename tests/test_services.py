"""Focused tests for the core business rules.

These tests avoid the full web stack and instead verify the calculations that
most directly affect the teacher's exported planning file.
"""

from datetime import date

import pytest
from openpyxl import load_workbook

from app.services.allocation import RAPlan, allocate_ra_hours, validate_ra_distribution
from app.services.calendar import build_schedule, expand_excluded_periods, total_available_hours
from app.services.export import build_workbook


def test_available_hours_calculation_uses_real_weekdays():
    """Only weekdays in the real date range should contribute hours."""

    schedule = build_schedule(
        date(2026, 9, 1),
        date(2026, 9, 7),
        {0: 2, 1: 3, 2: 4, 3: 1, 4: 5},
        set(),
    )
    assert total_available_hours(schedule) == 15


def test_holiday_ranges_are_excluded_without_duplicates():
    """Overlapping excluded periods should not subtract the same day twice."""

    excluded = expand_excluded_periods(
        [
            (date(2026, 9, 2), date(2026, 9, 4)),
            (date(2026, 9, 4), date(2026, 9, 5)),
        ]
    )
    schedule = build_schedule(date(2026, 9, 1), date(2026, 9, 7), {0: 2, 1: 2, 2: 2, 3: 2, 4: 2}, excluded)
    assert [item.date.isoformat() for item in schedule] == ["2026-09-01", "2026-09-07"]


def test_sequential_ra_allocation_can_split_same_day():
    """A day can contain the end of one RA and the start of the next."""

    schedule = build_schedule(date(2026, 9, 1), date(2026, 9, 2), {1: 4, 2: 4}, set())
    rows = allocate_ra_hours(schedule, [RAPlan("RA1", "RA1", 5), RAPlan("RA2", "RA2", 3)])
    assert rows[0]["ra_hours"] == {"RA1": 4, "RA2": 0}
    assert rows[1]["ra_hours"] == {"RA1": 1, "RA2": 3}


def test_distribution_validation_requires_exact_match():
    """Export must fail if the teacher leaves hours unassigned."""

    with pytest.raises(ValueError):
        validate_ra_distribution(10, [RAPlan("RA1", "RA1", 7), RAPlan("RA2", "RA2", 2)])


def test_export_uses_blank_cells_for_zero_ra_hours():
    """Zero-hour RA cells should stay visually empty in the spreadsheet."""

    workbook_io = build_workbook(
        [
            {
                "date": date(2026, 9, 1),
                "weekday": "Dimarts",
                "total_hours": 4,
                "ra_hours": {"RA1": 4, "RA2": 0},
            }
        ],
        [RAPlan("RA1", "RA1", 4), RAPlan("RA2", "RA2", 0)],
        {"Camp": "Valor"},
    )
    workbook = load_workbook(workbook_io)
    sheet = workbook["Calendari"]
    assert sheet["A2"].value == "dt."
    assert sheet["B2"].value.date().isoformat() == "2026-09-01"
    assert sheet["D2"].value == 4
    assert sheet["E2"].value is None
