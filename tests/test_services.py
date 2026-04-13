"""Focused tests for the core business rules.

These tests avoid the full web stack and instead verify the calculations that
most directly affect the teacher's exported planning file.
"""

from datetime import date

import pytest
from openpyxl import load_workbook

from app.date_utils import format_display_date, parse_date_input
from app.services.allocation import BlockPlan, RAPlan, allocate_ra_hours, allocate_ra_hours_by_blocks, validate_ra_distribution
from app.services.calendar import build_schedule, expand_excluded_periods, total_available_hours
from app.services.export import build_workbook


def test_available_hours_calculation_uses_real_weekdays():
    """Only teaching weekdays after the presentation day should contribute hours."""

    schedule = build_schedule(
        date(2026, 9, 1),
        date(2026, 9, 7),
        {0: 2, 1: 3, 2: 4, 3: 1, 4: 5},
        set(),
    )
    assert total_available_hours(schedule) == 12


def test_first_planning_day_is_always_excluded_from_schedule():
    """The first planning date should act as presentation day without classes."""

    schedule = build_schedule(
        date(2026, 9, 7),
        date(2026, 9, 9),
        {0: 2, 1: 2, 2: 2, 3: 0, 4: 0},
        set(),
    )
    assert [item.date.isoformat() for item in schedule] == ["2026-09-08", "2026-09-09"]


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


def test_parallel_blocks_preserve_their_weekly_split_when_both_need_all_hours():
    """Parallel blocks should stay in their own lanes when neither finishes early."""

    schedule = build_schedule(
        date(2026, 9, 7),
        date(2026, 9, 16),
        {0: 2, 2: 2},
        set(),
    )
    rows = allocate_ra_hours_by_blocks(
        schedule,
        [
            RAPlan("RA1", "RA1", 2, block_key="block_1"),
            RAPlan("RA2", "RA2", 6, block_key="block_2"),
        ],
        [
            BlockPlan("block_1", "Bloc 1", {0: 1, 1: 0, 2: 0, 3: 0, 4: 0}),
            BlockPlan("block_2", "Bloc 2", {0: 1, 1: 0, 2: 2, 3: 0, 4: 0}),
        ],
    )
    assert rows[0]["ra_hours"] == {"RA1": 1, "RA2": 1}
    assert rows[1]["ra_hours"] == {"RA1": 0, "RA2": 2}
    assert rows[2]["ra_hours"] == {"RA1": 1, "RA2": 1}
    assert rows[3]["ra_hours"] == {"RA1": 0, "RA2": 2}


def test_parallel_blocks_automatically_transfer_unused_hours():
    """Unused hours from one block should be absorbed by the other block automatically."""

    schedule = build_schedule(
        date(2026, 9, 7),
        date(2026, 9, 16),
        {0: 2, 2: 2},
        set(),
    )
    rows = allocate_ra_hours_by_blocks(
        schedule,
        [
            RAPlan("RA1", "RA1", 1, block_key="block_1"),
            RAPlan("RA2", "RA2", 7, block_key="block_2"),
        ],
        [
            BlockPlan("block_1", "Bloc 1", {0: 1, 1: 0, 2: 0, 3: 0, 4: 0}),
            BlockPlan("block_2", "Bloc 2", {0: 1, 1: 0, 2: 2, 3: 0, 4: 0}),
        ],
    )
    assert rows[0]["ra_hours"] == {"RA1": 1, "RA2": 1}
    assert rows[1]["ra_hours"] == {"RA1": 0, "RA2": 2}
    assert rows[2]["ra_hours"] == {"RA1": 0, "RA2": 2}
    assert rows[3]["ra_hours"] == {"RA1": 0, "RA2": 2}


def test_parallel_blocks_can_transfer_unused_hours_in_reverse_direction():
    """If block 2 finishes early, its spare hours should move to block 1."""

    schedule = build_schedule(
        date(2026, 9, 7),
        date(2026, 9, 16),
        {0: 2, 2: 2},
        set(),
    )
    rows = allocate_ra_hours_by_blocks(
        schedule,
        [
            RAPlan("RA1", "RA1", 7, block_key="block_1"),
            RAPlan("RA2", "RA2", 1, block_key="block_2"),
        ],
        [
            BlockPlan("block_1", "Bloc 1", {0: 1, 1: 0, 2: 0, 3: 0, 4: 0}),
            BlockPlan("block_2", "Bloc 2", {0: 1, 1: 0, 2: 2, 3: 0, 4: 0}),
        ],
    )
    assert rows[0]["ra_hours"] == {"RA1": 1, "RA2": 1}
    assert rows[1]["ra_hours"] == {"RA1": 2, "RA2": 0}
    assert rows[2]["ra_hours"] == {"RA1": 2, "RA2": 0}
    assert rows[3]["ra_hours"] == {"RA1": 2, "RA2": 0}


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
    assert "A1:B1" in [str(range_ref) for range_ref in sheet.merged_cells.ranges]
    assert sheet["A1"].value == "Data"
    assert sheet["A1"].alignment.horizontal == "left"
    assert sheet["A2"].value == "dt."
    assert sheet["B2"].value.date().isoformat() == "2026-09-01"
    assert sheet["B2"].number_format == "DD/MM/YYYY"
    assert sheet["C1"].value == "Hores"
    assert sheet.column_dimensions["C"].width < 16
    assert sheet["C1"].alignment.horizontal == "center"
    assert sheet["C2"].alignment.horizontal == "center"
    assert sheet["D1"].alignment.horizontal == "center"
    assert sheet["D2"].alignment.horizontal == "center"
    assert sheet["D1"].fill.fgColor.rgb == "00E7EFD8"
    assert sheet["A1"].border.left.style == "thin"
    assert sheet["D2"].value == 4
    assert sheet["E2"].value is None


def test_export_marks_new_ra_start_rows_with_light_fill():
    """Rows where a new RA starts should be visually highlighted."""

    workbook_io = build_workbook(
        [
            {
                "date": date(2026, 9, 1),
                "weekday": "Dimarts",
                "total_hours": 1,
                "ra_hours": {"RA1": 1, "RA2": 0},
            },
            {
                "date": date(2026, 9, 8),
                "weekday": "Dimarts",
                "total_hours": 1,
                "ra_hours": {"RA1": 0, "RA2": 1},
            },
        ],
        [RAPlan("RA1", "RA1", 1), RAPlan("RA2", "RA2", 1)],
        {"Camp": "Valor"},
    )
    workbook = load_workbook(workbook_io)
    sheet = workbook["Calendari"]
    assert sheet["A3"].fill.fgColor.rgb == "00E9E9E9"
    assert sheet["D3"].fill.fgColor.rgb == "00E9E9E9"


def test_parse_date_input_accepts_dd_mm_yyyy():
    """The web UI should accept dates in the requested Catalan-style format."""

    assert parse_date_input("09/12/2025") == date(2025, 12, 9)


def test_parse_date_input_accepts_single_digit_day_and_month():
    """Manual date entry should not require leading zeroes."""

    assert parse_date_input("7/1/2026") == date(2026, 1, 7)


def test_parse_date_input_accepts_two_digit_year():
    """Manual date entry should also accept a two-digit year."""

    assert parse_date_input("7/11/26") == date(2026, 11, 7)


def test_parse_date_input_keeps_iso_backwards_compatible():
    """Older saved forms or direct POSTs using ISO dates should still work."""

    assert parse_date_input("2025-12-09") == date(2025, 12, 9)


def test_format_display_date_returns_dd_mm_yyyy():
    """Visible dates should always render in DD/MM/YYYY."""

    assert format_display_date(date(2026, 5, 27)) == "27/05/2026"
