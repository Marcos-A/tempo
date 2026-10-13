"""Day-by-day calculation for student internship calendars.

Every value is kept in minutes so daily schedules such as 4 h 30 min stay
exact; conversion to hours only happens when presenting or exporting.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

from app.services.calendar import WEEKDAY_NAMES

# Safety net so an all-zero schedule cannot loop forever: no internship
# realistically spans more than two years.
MAX_INTERNSHIP_DAYS = 2 * 366
MAX_DAILY_HOURS = 12

DAY_KIND_WORKING = "working"
DAY_KIND_HOLIDAY = "holiday"
DAY_KIND_WEEKEND = "weekend"
DAY_KIND_OVERRIDE = "override"


@dataclass(frozen=True)
class InternshipDay:
    """One calendar date between the start and the computed end date."""

    date: date
    minutes: int
    default_minutes: int
    kind: str
    cumulative_minutes: int
    label: str = ""
    is_partial: bool = False

    @property
    def weekday_name(self) -> str:
        return WEEKDAY_NAMES[self.date.weekday()]


@dataclass(frozen=True)
class InternshipCalendar:
    """Result of walking the calendar until the target minutes are reached."""

    start_date: date
    target_minutes: int
    days: list[InternshipDay] = field(default_factory=list)

    @property
    def end_date(self) -> date:
        return self.days[-1].date

    @property
    def scheduled_minutes(self) -> int:
        return self.days[-1].cumulative_minutes if self.days else 0

    @property
    def working_day_count(self) -> int:
        return sum(1 for day in self.days if day.minutes > 0)


def default_minutes_for(
    current: date,
    weekday_minutes: dict[int, int],
    non_working_dates: set[date],
) -> int:
    """Return the minutes a date would get without any per-day override."""

    if current in non_working_dates:
        return 0
    return weekday_minutes.get(current.weekday(), 0)


def classify_day(
    current: date,
    minutes: int,
    default_minutes: int,
    is_overridden: bool,
    non_working_dates: set[date],
) -> str:
    """Pick the colour category used by the preview and the XLSX export."""

    if is_overridden and minutes != default_minutes:
        return DAY_KIND_OVERRIDE
    if current in non_working_dates:
        return DAY_KIND_HOLIDAY
    if default_minutes == 0:
        return DAY_KIND_WEEKEND
    return DAY_KIND_WORKING


def build_internship_calendar(
    start_date: date,
    target_minutes: int,
    weekday_minutes: dict[int, int],
    non_working_dates: set[date],
    overrides: dict[date, int] | None = None,
    labels_by_date: dict[date, str] | None = None,
) -> InternshipCalendar:
    """Walk forward from `start_date` adding daily minutes until the target is met.

    `weekday_minutes` maps Monday=0..Sunday=6 to default minutes; missing
    weekdays count as zero. `overrides` replaces the minutes of specific dates,
    including adding time on weekends or holidays. The last day only receives
    the remaining minutes, so the total never exceeds the target.
    """

    if target_minutes <= 0:
        raise ValueError("Indica un total d'hores de pràctiques superior a zero.")

    overrides = overrides or {}
    labels_by_date = labels_by_date or {}
    has_future_override_time = any(minutes > 0 and day >= start_date for day, minutes in overrides.items())
    if not any(minutes > 0 for minutes in weekday_minutes.values()) and not has_future_override_time:
        raise ValueError("Indica com a mínim un dia de la setmana amb hores de pràctiques.")

    days: list[InternshipDay] = []
    cumulative = 0
    current = start_date
    while cumulative < target_minutes:
        if len(days) >= MAX_INTERNSHIP_DAYS:
            raise ValueError(
                "Amb aquest horari les pràctiques durarien més de dos anys. Revisa les hores diàries i els dies no laborables."
            )
        default_minutes = default_minutes_for(current, weekday_minutes, non_working_dates)
        is_overridden = current in overrides
        planned = overrides[current] if is_overridden else default_minutes
        remaining = target_minutes - cumulative
        minutes = min(planned, remaining)
        cumulative += minutes
        days.append(
            InternshipDay(
                date=current,
                minutes=minutes,
                default_minutes=default_minutes,
                kind=classify_day(current, planned, default_minutes, is_overridden, non_working_dates),
                cumulative_minutes=cumulative,
                label=labels_by_date.get(current, ""),
                is_partial=0 < minutes < planned,
            )
        )
        current += timedelta(days=1)

    return InternshipCalendar(start_date=start_date, target_minutes=target_minutes, days=days)
