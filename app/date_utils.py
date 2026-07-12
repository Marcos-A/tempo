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
