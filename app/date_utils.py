"""Helpers for parsing and formatting user-facing dates."""

import re
from datetime import date, datetime


DISPLAY_DATE_FORMAT = "%d/%m/%Y"
CATALAN_MONTH_NAMES = [
    "Gener", "Febrer", "Març", "Abril", "Maig", "Juny",
    "Juliol", "Agost", "Setembre", "Octubre", "Novembre", "Desembre",
]


def format_display_date(value: date) -> str:
    """Return a calendar date in the UI's fixed DD/MM/YYYY format."""

    return value.strftime(DISPLAY_DATE_FORMAT)


def format_month_label(value: date) -> str:
    """Return a Catalan 'Month YYYY' label for grouping dates by month."""

    return f"{CATALAN_MONTH_NAMES[value.month - 1]} {value.year}"


def parse_date_input(value: str) -> date:
    """Accept D/M/YY, D/M/YYYY, and ISO dates from the UI."""

    candidate = value.strip()
    if not candidate:
        raise ValueError("Introdueix una data en format D/M/AA o D/M/AAAA.")

    try:
        return date.fromisoformat(candidate)
    except ValueError:
        pass

    match = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{2}|\d{4})", candidate)
    if match:
        day_text, month_text, year_text = match.groups()
        day = int(day_text)
        month = int(month_text)
        year = int(year_text)
        if len(year_text) == 2:
            year += 2000
        try:
            return date(year, month, day)
        except ValueError:
            pass

    raise ValueError("Introdueix una data en format D/M/AA o D/M/AAAA.")


def format_day_month(day: int, month: int) -> str:
    """Return a yearly date in DD/MM format."""

    return f"{day:02d}/{month:02d}"


def parse_day_month_input(value: str) -> tuple[int, int]:
    """Accept D/M for a holiday that repeats every year; return (day, month)."""

    match = re.fullmatch(r"(\d{1,2})/(\d{1,2})", value.strip())
    if match:
        day, month = int(match.group(1)), int(match.group(2))
        if (day, month) == (29, 2):
            raise ValueError("El 29 de febrer no es repeteix cada any.")
        try:
            # 2001 is not a leap year, so this only accepts real yearly dates.
            date(2001, month, day)
        except ValueError:
            pass
        else:
            return day, month
    raise ValueError("Introdueix el dia i el mes en format D/M (p. ex. 1/5).")
