"""Logic for validating and distributing RA hours across real teaching dates."""

from __future__ import annotations

from dataclasses import dataclass

from app.services.calendar import ScheduleDay


@dataclass(frozen=True)
class RAPlan:
    """Teacher-defined total hours for one learning outcome."""

    key: str
    name: str
    hours: int


def validate_ra_distribution(total_available: int, ras: list[RAPlan]) -> None:
    """Ensure the RA totals are complete and internally valid before export."""

    total_assigned = sum(item.hours for item in ras)
    if total_assigned != total_available:
        raise ValueError("Les hores assignades a les RAs han de coincidir exactament amb les hores disponibles.")
    if any(item.hours < 0 for item in ras):
        raise ValueError("Les hores de les RAs no poden ser negatives.")


def allocate_ra_hours(schedule: list[ScheduleDay], ras: list[RAPlan]) -> list[dict[str, object]]:
    """Fill the calendar in chronological order using the selected RA order.

    A single day can contain hours from more than one RA when one RA finishes
    partway through that day and the next RA continues in the remaining capacity.
    """

    validate_ra_distribution(sum(day.hours for day in schedule), ras)

    rows: list[dict[str, object]] = []
    ra_index = 0
    remaining_for_ra = ras[0].hours if ras else 0

    for day in schedule:
        row: dict[str, object] = {
            "date": day.date,
            "weekday": day.weekday_name,
            "total_hours": day.hours,
            "ra_hours": {ra.key: 0 for ra in ras},
        }
        remaining_on_day = day.hours

        while remaining_on_day > 0 and ra_index < len(ras):
            if remaining_for_ra == 0:
                # Move to the next RA as soon as the current one has consumed
                # all of its assigned hours.
                ra_index += 1
                if ra_index >= len(ras):
                    break
                remaining_for_ra = ras[ra_index].hours
                continue

            # Never allocate more than the day can hold or the RA still needs.
            allocated = min(remaining_on_day, remaining_for_ra)
            row["ra_hours"][ras[ra_index].key] += allocated
            remaining_on_day -= allocated
            remaining_for_ra -= allocated

        if remaining_on_day != 0:
            raise ValueError("L'assignació ha deixat hores sense distribuir en un dia lectiu.")
        rows.append(row)

    return rows
