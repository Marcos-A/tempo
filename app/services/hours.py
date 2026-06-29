"""Helpers for presenting and converting teaching time values."""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

MINUTES_PER_HOUR = 60
BLOCK_MINUTE_CHOICES = tuple(range(0, 60, 5))
DISPLAY_HOUR_QUANTUM = Decimal("0.01")


def parse_hour_minute_pair(hours_raw: str, minutes_raw: str, *, max_hours: int = 6) -> int:
    """Validate one hours+minutes pair and return the total as minutes."""

    hours = int(hours_raw or 0)
    minutes = int(minutes_raw or 0)
    if hours < 0 or hours > max_hours:
        raise ValueError(f"Les hores dels blocs han d'estar entre 0 i {max_hours}.")
    if minutes not in BLOCK_MINUTE_CHOICES:
        raise ValueError("Els minuts dels blocs han d'avançar en trams de 5 minuts.")
    return (hours * MINUTES_PER_HOUR) + minutes


def minutes_to_hour_number(minutes: int) -> int | float:
    """Convert exact minutes into an XLSX/JSON-friendly hour number."""

    if minutes % MINUTES_PER_HOUR == 0:
        return minutes // MINUTES_PER_HOUR
    return float((Decimal(minutes) / MINUTES_PER_HOUR).quantize(DISPLAY_HOUR_QUANTUM, rounding=ROUND_HALF_UP))


def format_minutes_label(minutes: int) -> str:
    """Render a minute count in a teacher-friendly Catalan label."""

    hours, remaining_minutes = divmod(int(minutes), MINUTES_PER_HOUR)
    if hours and remaining_minutes:
        return f"{hours} h {remaining_minutes:02d} min"
    if hours:
        return f"{hours} h"
    return f"{remaining_minutes} min"
