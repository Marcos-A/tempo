"""Logic for validating and distributing RA hours across real teaching dates."""

from __future__ import annotations

from dataclasses import dataclass

from app.services.calendar import ScheduleDay
from app.services.hours import MINUTES_PER_HOUR, minutes_to_hour_number


@dataclass(frozen=True)
class RAPlan:
    """Teacher-defined total hours for one learning outcome."""

    key: str
    name: str
    hours: int | float
    block_key: str | None = None
    minutes: int | None = None


@dataclass(frozen=True)
class BlockPlan:
    """One weekly teaching lane within the parallel planning mode."""

    key: str
    name: str
    weekday_minutes: dict[int, int]
    starts_after_ra: str | None = None


def _ra_total_minutes(ra: RAPlan) -> int:
    """Return the exact minutes assigned to one RA."""

    if ra.minutes is not None:
        return int(ra.minutes)
    return int(ra.hours * MINUTES_PER_HOUR)


def validate_ra_distribution(total_available: int, ras: list[RAPlan], *, use_minutes: bool = False) -> None:
    """Ensure the RA totals are complete and internally valid before export."""

    assigned_values = [_ra_total_minutes(item) if use_minutes else item.hours for item in ras]
    total_assigned = sum(assigned_values)
    if total_assigned != total_available:
        raise ValueError("Les hores assignades a les RAs han de coincidir exactament amb les hores disponibles.")
    if any(value < 0 for value in assigned_values):
        raise ValueError("Les hores de les RAs no poden ser negatives.")
    if any(value == 0 for value in assigned_values):
        raise ValueError("Cada RA ha de tenir temps assignat abans d'exportar.")


def _allocate_block_minutes(
    capacity_minutes: int,
    block_ras: list[RAPlan],
    state: dict[str, int],
    row_minutes: dict[str, int],
) -> int:
    """Allocate one block's daily capacity in minutes and return any leftovers."""

    remaining_capacity = capacity_minutes
    while remaining_capacity > 0 and state["index"] < len(block_ras):
        current_ra = block_ras[state["index"]]
        if state["remaining"] == 0:
            state["index"] += 1
            if state["index"] >= len(block_ras):
                break
            current_ra = block_ras[state["index"]]
            state["remaining"] = _ra_total_minutes(current_ra)

        allocated = min(remaining_capacity, state["remaining"])
        row_minutes[current_ra.key] += allocated
        remaining_capacity -= allocated
        state["remaining"] -= allocated

    return remaining_capacity


def block_day_capacities(
    day: ScheduleDay, blocks: list[BlockPlan], finished_ra_keys: set[str]
) -> dict[str, int]:
    """Return each block's effective teaching minutes for one schedule day.

    A block whose `starts_after_ra` RA has not finished yet (as of the end of
    the previous schedule day) contributes zero minutes that day; that slice
    is folded into the block(s) that have already started (at most one block
    may carry a trigger, enforced when the blocks are built), so the
    calendar's daily hours are never lost.
    """

    capacities = {block.key: block.weekday_minutes.get(day.weekday_index, 0) for block in blocks}
    started_keys = [
        block.key
        for block in blocks
        if not block.starts_after_ra or block.starts_after_ra in finished_ra_keys
    ]
    delayed_keys = [block.key for block in blocks if block.key not in started_keys]
    borrowed = sum(capacities[key] for key in delayed_keys)
    for key in delayed_keys:
        capacities[key] = 0
    if borrowed and started_keys:
        capacities[started_keys[0]] += borrowed
    return capacities


def _block_has_pending_hours(state: dict[str, int], block_ras: list[RAPlan]) -> bool:
    """Tell whether a block still has RA hours left to allocate."""

    if not block_ras or state["index"] >= len(block_ras):
        return False
    if state["remaining"] > 0:
        return True
    return state["index"] < len(block_ras) - 1


def allocate_ra_hours_by_blocks(
    schedule: list[ScheduleDay],
    ras: list[RAPlan],
    blocks: list[BlockPlan],
) -> list[dict[str, object]]:
    """Allocate hours across parallel blocks, auto-redistributing unused block hours."""

    validate_ra_distribution(sum(day.hours for day in schedule) * MINUTES_PER_HOUR, ras, use_minutes=True)
    block_map = {block.key: block for block in blocks}
    invalid_blocks = sorted({ra.block_key for ra in ras if ra.block_key not in block_map})
    if invalid_blocks:
        raise ValueError("Cada RA ha d'estar assignada a un bloc vàlid.")

    ra_by_key = {ra.key: ra for ra in ras}
    for block in blocks:
        if not block.starts_after_ra:
            continue
        trigger_ra = ra_by_key.get(block.starts_after_ra)
        if trigger_ra is None:
            raise ValueError("El bloc espera una RA que no existeix en aquesta planificació.")
        if trigger_ra.block_key == block.key:
            raise ValueError("Un bloc no pot començar després d'una RA que ell mateix imparteix.")

    block_ras: dict[str, list[RAPlan]] = {block.key: [ra for ra in ras if ra.block_key == block.key] for block in blocks}
    block_states: dict[str, dict[str, int]] = {}
    for block in blocks:
        ras_in_block = block_ras[block.key]
        block_states[block.key] = {
            "index": 0,
            "remaining": _ra_total_minutes(ras_in_block[0]) if ras_in_block else 0,
        }

    ra_target_minutes = {ra.key: _ra_total_minutes(ra) for ra in ras}
    ra_cumulative_minutes = {ra.key: 0 for ra in ras}
    finished_ra_keys: set[str] = set()

    rows: list[dict[str, object]] = []
    for day in schedule:
        row: dict[str, object] = {
            "date": day.date,
            "weekday": day.weekday_name,
            "total_hours": day.hours,
            "ra_hours": {ra.key: 0 for ra in ras},
        }
        row_minutes = {ra.key: 0 for ra in ras}
        released_minutes = 0
        day_capacities = block_day_capacities(day, blocks, finished_ra_keys)

        for block in blocks:
            capacity = day_capacities[block.key]
            if capacity == 0:
                continue

            remaining_capacity = _allocate_block_minutes(
                capacity,
                block_ras[block.key],
                block_states[block.key],
                row_minutes,
            )
            released_minutes += remaining_capacity

        if released_minutes:
            for block in blocks:
                if not _block_has_pending_hours(block_states[block.key], block_ras[block.key]):
                    continue
                released_minutes = _allocate_block_minutes(
                    released_minutes,
                    block_ras[block.key],
                    block_states[block.key],
                    row_minutes,
                )
                if released_minutes == 0:
                    break

        if released_minutes != 0:
            raise ValueError("L'assignació dels blocs ha deixat hores sense absorbir en un dia lectiu.")

        for ra_key, minutes in row_minutes.items():
            if minutes == 0 or ra_key in finished_ra_keys:
                continue
            ra_cumulative_minutes[ra_key] += minutes
            if ra_cumulative_minutes[ra_key] >= ra_target_minutes[ra_key]:
                finished_ra_keys.add(ra_key)

        row["ra_hours"] = {key: minutes_to_hour_number(minutes) for key, minutes in row_minutes.items()}
        rows.append(row)

    return rows


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
                ra_index += 1
                if ra_index >= len(ras):
                    break
                remaining_for_ra = ras[ra_index].hours
                continue

            allocated = min(remaining_on_day, remaining_for_ra)
            row["ra_hours"][ras[ra_index].key] += allocated
            remaining_on_day -= allocated
            remaining_for_ra -= allocated

        if remaining_on_day != 0:
            raise ValueError("L'assignació ha deixat hores sense distribuir en un dia lectiu.")
        rows.append(row)

    return rows
