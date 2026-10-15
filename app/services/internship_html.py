"""Read-only HTML export for internship calendars.

The file is a snapshot of the planner's "Calendari resultant": the same
summary, legend and month grids, with the stylesheet, font and logo inlined
so it opens offline and prints without the app. It contains no executable
script; the plan's inputs travel in an inert JSON block so a future import
could load the file back into the planner.

The PDF export renders the same template (with `pdf` set) through
WeasyPrint, adding the page layout from `static/css/internship-pdf.css`
(inlined after the app stylesheet so it wins over it).

Keep in step with the web planner: `renderResult` in
`templates/internship/index.html` draws the same month grid in JavaScript.
Both share the day labels and legend defined here and the CSS classes in
`static/css/app.css`, but a change to the grid markup (a new marker, class
or tooltip detail) has to be made in both places.
"""

from __future__ import annotations

import base64
from datetime import date
from functools import lru_cache
from pathlib import Path

from app.date_utils import format_display_date, format_month_label
from app.services.hours import MINUTES_PER_HOUR, format_minutes_label
from app.services.internship import (
    DAY_KIND_HOLIDAY,
    DAY_KIND_OVERRIDE,
    DAY_KIND_WEEKEND,
    DAY_KIND_WORKING,
    InternshipCalendar,
)
from app.services.internship_export import WEEKDAY_SHORT, month_starts


STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
FONT_URL = 'url("../fonts/inter-latin-variable.woff2")'

# Day categories as the planner's legend and tooltips name them (the web page
# reads this through its template too).
CALENDAR_KIND_LABELS = {
    DAY_KIND_WORKING: "Laborable",
    DAY_KIND_HOLIDAY: "Festiu / no lectiu",
    DAY_KIND_WEEKEND: "Sense horari",
    DAY_KIND_OVERRIDE: "Hores canviades a mà",
}


def _data_uri(path: Path, media_type: str) -> str:
    return f"data:{media_type};base64,{base64.b64encode(path.read_bytes()).decode('ascii')}"


@lru_cache(maxsize=1)
def inline_stylesheet() -> str:
    """Return the app stylesheet with its font embedded, so the file needs no server."""

    css = (STATIC_DIR / "css" / "app.css").read_text(encoding="utf-8")
    font = _data_uri(STATIC_DIR / "fonts" / "inter-latin-variable.woff2", "font/woff2")
    return css.replace(FONT_URL, f'url("{font}")')


@lru_cache(maxsize=1)
def inline_logo() -> str:
    return _data_uri(STATIC_DIR / "img" / "tempo-lockup-pine.svg", "image/svg+xml")


@lru_cache(maxsize=1)
def pdf_stylesheet() -> str:
    return (STATIC_DIR / "css" / "internship-pdf.css").read_text(encoding="utf-8")


def render_pdf(html: str) -> bytes:
    """Lay out the rendered read-only copy (with `pdf` set) as A4 pages."""

    # Imported here so the rest of the app does not need WeasyPrint's system libraries.
    from weasyprint import HTML

    return HTML(string=html).write_pdf()


def format_compact(minutes: int) -> str:
    """Return the grid's short hours label, e.g. 7h or 4h30."""

    hours, remaining = divmod(minutes, MINUTES_PER_HOUR)
    return f"{hours}h{remaining:02d}" if remaining else f"{hours}h"


def build_month_views(result: InternshipCalendar) -> list[dict[str, object]]:
    """Describe each month of the calendar the way the planner draws it.

    Months run from the start month to the end date's month. Every cell is
    either a blank before the 1st, a date outside the internship, or a day of
    the internship with its colour class, hours and tooltip.
    """

    days_by_date = {day.date: day for day in result.days}
    has_schedule_changes = any(day.schedule_index > 0 for day in result.days)
    schedule_starts = {
        day.date for previous, day in zip(result.days, result.days[1:]) if day.schedule_index != previous.schedule_index
    }

    months: list[dict[str, object]] = []
    for month_start in month_starts(result.start_date, result.end_date):
        cells: list[dict[str, object]] = []
        month_minutes = 0
        current = month_start
        while current.month == month_start.month:
            day = days_by_date.get(current)
            if day is None:
                cells.append({"number": current.day, "day": None})
            else:
                month_minutes += day.minutes
                classes = [f"day-{day.kind}"]
                if result.is_complete and current == result.end_date:
                    classes.append("day-end")
                if current in schedule_starts:
                    classes.append("day-schedule-start")
                parts = [f"{WEEKDAY_SHORT[current.weekday()]} {format_display_date(current)}", CALENDAR_KIND_LABELS[day.kind]]
                if day.label:
                    parts.append(day.label)
                if current in schedule_starts:
                    parts.append(f"comença el període {day.schedule_index + 1}")
                elif has_schedule_changes:
                    parts.append(f"període {day.schedule_index + 1}")
                parts.append(format_minutes_label(day.minutes) if day.minutes else "sense hores")
                if day.is_partial:
                    parts.append("darrer dia parcial")
                cells.append(
                    {
                        "number": current.day,
                        "day": day,
                        "classes": " ".join(classes),
                        "hours": format_compact(day.minutes) if day.minutes else "–",
                        "title": " · ".join(parts),
                    }
                )
            current = date.fromordinal(current.toordinal() + 1)
        months.append(
            {
                "title": format_month_label(month_start),
                "total": format_minutes_label(month_minutes),
                "leading_blanks": month_start.weekday(),
                "cells": cells,
            }
        )
    return months


def has_schedule_starts(result: InternshipCalendar) -> bool:
    return any(day.schedule_index != previous.schedule_index for previous, day in zip(result.days, result.days[1:]))
