"""Calendar-building utilities used to turn dates into teaching capacity."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta


WEEKDAY_NAMES = ["Dilluns", "Dimarts", "Dimecres", "Dijous", "Divendres", "Dissabte", "Diumenge"]


@dataclass(frozen=True)
class ScheduleDay:
    """One valid teaching date after weekends and exclusions are removed."""

    date: date
    weekday_index: int
    weekday_name: str
    hours: int


def daterange(start_date: date, end_date: date) -> list[date]:
    """Return every calendar date in an inclusive range."""

    dates: list[date] = []
    current = start_date
    while current <= end_date:
        dates.append(current)
        current += timedelta(days=1)
    return dates


def expand_excluded_periods(periods: list[tuple[date, date]]) -> set[date]:
    """Expand stored ranges into a deduplicated set of excluded dates."""

    excluded_dates: set[date] = set()
    for start_date, end_date in periods:
        for current in daterange(start_date, end_date):
            excluded_dates.add(current)
    return excluded_dates


def build_schedule(
    start_date: date,
    end_date: date,
    weekday_hours: dict[int, int],
    excluded_dates: set[date],
) -> list[ScheduleDay]:
    """Build the real teaching schedule between two dates.

    Only Monday-Friday dates with positive configured hours are kept.
    Admin exclusions are removed before the final list is returned.
    """

    if end_date < start_date:
        raise ValueError("End date cannot be before start date.")

    schedule: list[ScheduleDay] = []
    for current_date in daterange(start_date, end_date):
        weekday_index = current_date.weekday()
        if weekday_index > 4:
            # Weekends never count as teaching dates in this MVP.
            continue
        if current_date in excluded_dates:
            continue

        hours = weekday_hours.get(weekday_index, 0)
        if hours <= 0:
            # A weekday can exist in the range but still be unavailable if the
            # teacher set zero hours for that day of the week.
            continue

        schedule.append(
            ScheduleDay(
                date=current_date,
                weekday_index=weekday_index,
                weekday_name=WEEKDAY_NAMES[weekday_index],
                hours=hours,
            )
        )
    return schedule


def total_available_hours(schedule: list[ScheduleDay]) -> int:
    """Sum the teaching capacity across the prepared schedule."""

    return sum(day.hours for day in schedule)
