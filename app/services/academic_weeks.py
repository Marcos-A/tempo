"""Helpers for mapping calendar dates to admin-assigned academic week numbers.

Weeks are always identified by their Monday (`week_start_date`), so a week's
end is implicit six days later and never needs to be kept in sync separately.
"""

from __future__ import annotations

from datetime import date, timedelta


def week_start(value: date) -> date:
    """Return the Monday that starts the calendar week containing this date."""

    return value - timedelta(days=value.weekday())


def iter_week_starts(start_date: date, end_date: date) -> list[date]:
    """Return every Monday whose week overlaps the given inclusive date range."""

    if end_date < start_date:
        raise ValueError("End date cannot be before start date.")

    week_starts: list[date] = []
    current = week_start(start_date)
    last = week_start(end_date)
    while current <= last:
        week_starts.append(current)
        current += timedelta(days=7)
    return week_starts


def week_has_teaching_potential(monday: date, excluded_dates: set[date]) -> bool:
    """Tell whether at least one weekday in this week is not fully excluded."""

    return any((monday + timedelta(days=offset)) not in excluded_dates for offset in range(5))


def suggest_week_numbers(week_starts: list[date], excluded_dates: set[date]) -> dict[date, int]:
    """Suggest sequential numbers for weeks that still have teaching potential.

    Fully-excluded weeks (e.g. a whole week inside a vacation period) are
    skipped rather than numbered, mirroring how the school's own planning
    document leaves them out.
    """

    suggestions: dict[date, int] = {}
    next_number = 1
    for monday in week_starts:
        if not week_has_teaching_potential(monday, excluded_dates):
            continue
        suggestions[monday] = next_number
        next_number += 1
    return suggestions


def week_number_for_date(value: date, saved_numbers: dict[date, int]) -> int | None:
    """Look up the admin-assigned number for the week containing this date."""

    return saved_numbers.get(week_start(value))
