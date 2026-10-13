"""Routes for the internship calendar planner.

The page recalculates live through `/practiques/calcul` (JSON) and downloads
the workbook through `/practiques/export`. Both endpoints receive the same
JSON payload and run the same validation, so the exported file always
matches the preview.
"""

from __future__ import annotations

import json
import re
import unicodedata
from datetime import date

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse, RedirectResponse, StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.date_utils import format_display_date, parse_date_input
from app.models import AcademicYear, ExcludedPeriod
from app.routes.teacher import templates
from app.services.academic_years import get_active_academic_year
from app.services.calendar import daterange
from app.services.hours import BLOCK_MINUTE_CHOICES, MINUTES_PER_HOUR, format_minutes_label
from app.services.internship import MAX_DAILY_HOURS, InternshipCalendar, build_internship_calendar
from app.services.internship_export import METADATA_FIELDS, build_internship_workbook, calendar_grid_end


router = APIRouter(prefix="/practiques", tags=["internship"])

MAX_TARGET_HOURS = 3000
MAX_EXTRA_PERIODS = 100
MAX_LABEL_LENGTH = 120
MAX_METADATA_LENGTH = 200
METADATA_KEYS = tuple(key for key, _ in METADATA_FIELDS)


def _parse_minutes(value: object, *, max_hours: int, field_label: str) -> int:
    """Validate an exact minute count in 5-minute steps."""

    try:
        minutes = int(value or 0)
    except (TypeError, ValueError):
        raise ValueError(f"{field_label}: valor no vàlid.") from None
    if minutes < 0 or minutes > max_hours * MINUTES_PER_HOUR:
        raise ValueError(f"{field_label}: ha d'estar entre 0 i {max_hours} h.")
    if minutes % BLOCK_MINUTE_CHOICES[1]:
        raise ValueError(f"{field_label}: els minuts han d'avançar en trams de 5.")
    return minutes


def _school_periods(db: Session) -> list[ExcludedPeriod]:
    """Return every configured non-working period, oldest first.

    Periods from all academic years are offered so an internship that runs
    into the next school year still sees that year's holidays.
    """

    return db.scalars(select(ExcludedPeriod).order_by(ExcludedPeriod.start_date, ExcludedPeriod.id)).all()


class InternshipRequest:
    """Validated inputs shared by the live preview and the export."""

    def __init__(self, payload: dict, periods: list[ExcludedPeriod]):
        if not isinstance(payload, dict):
            raise ValueError("Dades de càlcul no vàlides.")

        self.start_date = parse_date_input(str(payload.get("start_date") or ""))

        try:
            target_hours = int(payload.get("target_hours") or 0)
        except (TypeError, ValueError):
            raise ValueError("Indica el total d'hores de pràctiques.") from None
        if target_hours < 0 or target_hours > MAX_TARGET_HOURS:
            raise ValueError(f"El total d'hores ha d'estar entre 1 i {MAX_TARGET_HOURS}.")
        target_extra = _parse_minutes(payload.get("target_minutes"), max_hours=1, field_label="Minuts del total")
        if target_extra >= MINUTES_PER_HOUR:
            raise ValueError("Minuts del total: valor no vàlid.")
        self.target_minutes = target_hours * MINUTES_PER_HOUR + target_extra
        if self.target_minutes <= 0:
            raise ValueError("Indica el total d'hores de pràctiques.")

        raw_weekdays = payload.get("weekday_minutes") or {}
        weekday_labels = ("Dilluns", "Dimarts", "Dimecres", "Dijous", "Divendres")
        self.weekday_minutes = {
            index: _parse_minutes(raw_weekdays.get(str(index)), max_hours=MAX_DAILY_HOURS, field_label=label)
            for index, label in enumerate(weekday_labels)
        }

        try:
            selected_ids = {int(value) for value in payload.get("excluded_period_ids") or []}
        except (TypeError, ValueError):
            raise ValueError("Selecció de períodes no lectius no vàlida.") from None
        self.school_periods = [period for period in periods if period.id in selected_ids]

        raw_extra = payload.get("extra_periods") or []
        if len(raw_extra) > MAX_EXTRA_PERIODS:
            raise ValueError("Hi ha massa dies no lectius afegits.")
        self.extra_periods: list[tuple[date, date, str]] = []
        for item in raw_extra:
            start = parse_date_input(str(item.get("start") or ""))
            end_text = str(item.get("end") or "").strip()
            end = parse_date_input(end_text) if end_text else start
            if end < start:
                raise ValueError("Un període no lectiu afegit acaba abans de començar.")
            label = str(item.get("label") or "").strip()[:MAX_LABEL_LENGTH]
            self.extra_periods.append((start, end, label))

        self.overrides: dict[date, int] = {}
        for key, value in (payload.get("overrides") or {}).items():
            try:
                override_date = date.fromisoformat(key)
            except ValueError:
                raise ValueError("Hi ha un dia modificat amb una data no vàlida.") from None
            self.overrides[override_date] = _parse_minutes(
                value, max_hours=MAX_DAILY_HOURS, field_label=f"Hores del {format_display_date(override_date)}"
            )

        raw_metadata = payload.get("metadata") or {}
        self.metadata = {key: str(raw_metadata.get(key) or "").strip()[:MAX_METADATA_LENGTH] for key in METADATA_KEYS}

    def non_working(self) -> tuple[set[date], dict[date, str]]:
        """Expand the selected school periods and extra dates into a lookup."""

        dates: set[date] = set()
        labels: dict[date, str] = {}
        ranges = [(p.start_date, p.end_date, (p.label or "").strip()) for p in self.school_periods] + self.extra_periods
        for start, end, label in ranges:
            for current in daterange(start, end):
                dates.add(current)
                if label and current not in labels:
                    labels[current] = label
        return dates, labels

    def calculate(self) -> InternshipCalendar:
        dates, labels = self.non_working()
        return build_internship_calendar(
            self.start_date,
            self.target_minutes,
            self.weekday_minutes,
            dates,
            self.overrides,
            labels,
        )

    def applied_periods(self, result: InternshipCalendar) -> list[dict[str, str]]:
        """Describe the periods that overlap the exported calendar, which runs past the end date."""

        grid_end = calendar_grid_end(result)
        applied: list[dict[str, str]] = []
        for period in self.school_periods:
            if period.end_date >= result.start_date and period.start_date <= grid_end:
                applied.append(
                    {
                        "start": format_display_date(period.start_date),
                        "end": format_display_date(period.end_date),
                        "label": (period.label or "").strip(),
                        "source": "Calendari del centre",
                    }
                )
        for start, end, label in self.extra_periods:
            if end >= result.start_date and start <= grid_end:
                applied.append(
                    {
                        "start": format_display_date(start),
                        "end": format_display_date(end),
                        "label": label,
                        "source": "Afegit manualment",
                    }
                )
        return applied


def _error_message(exc: Exception) -> str:
    """Our own validation errors are user-facing Catalan; anything else is malformed input."""

    if isinstance(exc, ValueError) and not isinstance(exc, json.JSONDecodeError):
        return str(exc)
    return "Dades de càlcul no vàlides."


def _coverage_warning(db: Session, result: InternshipCalendar) -> str | None:
    """Warn when the internship runs past the last configured academic year."""

    last_year_end = db.scalar(select(AcademicYear.default_end_date).order_by(AcademicYear.default_end_date.desc()))
    if last_year_end is not None and result.end_date > last_year_end:
        return (
            f"El calendari del centre només té dies no lectius configurats fins al {format_display_date(last_year_end)}. "
            "Afegeix a mà els festius posteriors."
        )
    return None


def _serialize_result(result: InternshipCalendar, warning: str | None) -> dict[str, object]:
    return {
        "ok": True,
        "start_date": result.start_date.isoformat(),
        "end_date": result.end_date.isoformat(),
        "end_date_display": format_display_date(result.end_date),
        "target_display": format_minutes_label(result.target_minutes),
        "scheduled_minutes": result.scheduled_minutes,
        "scheduled_display": format_minutes_label(result.scheduled_minutes),
        "working_days": result.working_day_count,
        "calendar_days": len(result.days),
        "warning": warning,
        "days": [
            {
                "date": day.date.isoformat(),
                "minutes": day.minutes,
                "default_minutes": day.default_minutes,
                "kind": day.kind,
                "label": day.label,
                "partial": day.is_partial,
            }
            for day in result.days
        ],
    }


def _export_filename(metadata: dict[str, str]) -> str:
    """Build an ASCII-safe filename, adding the student's name when present."""

    student = unicodedata.normalize("NFKD", metadata.get("student_name", "")).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^A-Za-z0-9]+", "-", student).strip("-").lower()
    return f"calendari-practiques-{slug}.xlsx" if slug else "calendari-practiques.xlsx"


def _render_page(request: Request, db: Session, *, state: dict | None = None, error: str | None = None, status_code: int = 200):
    active_year = get_active_academic_year(db)
    periods = _school_periods(db)
    default_state = {
        "start_date": format_display_date(date.today()),
        "target_hours": "",
        "target_minutes": 0,
        "weekday_minutes": {str(index): 0 for index in range(5)},
        "excluded_period_ids": [period.id for period in periods],
        "extra_periods": [],
        "overrides": {},
        "metadata": {key: "" for key in METADATA_KEYS},
    }
    return templates.TemplateResponse(
        request,
        "internship/index.html",
        {
            "title": "Calendari de pràctiques",
            "brand_tagline": "Planificador d'hores de pràctiques",
            "error": error,
            "active_year": active_year,
            "metadata_fields": METADATA_FIELDS,
            "max_daily_hours": MAX_DAILY_HOURS,
            "school_periods": [
                {
                    "id": period.id,
                    "start": period.start_date.isoformat(),
                    "end": period.end_date.isoformat(),
                    "display": (
                        format_display_date(period.start_date)
                        if period.start_date == period.end_date
                        else f"{format_display_date(period.start_date)} – {format_display_date(period.end_date)}"
                    ),
                    "label": (period.label or "").strip(),
                }
                for period in periods
            ],
            "state": state or default_state,
        },
        status_code=status_code,
    )


@router.get("")
def internship_page(request: Request, db: Session = Depends(get_db)):
    """Render the internship calendar planner."""

    return _render_page(request, db)


@router.get("/export")
def redirect_stray_export():
    """A plain GET on the export URL (bookmark, refresh) goes back to the planner."""

    return RedirectResponse(url="/practiques", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/calcul")
async def calculate_internship(request: Request, db: Session = Depends(get_db)):
    """Return the computed calendar as JSON for the live preview."""

    try:
        payload = json.loads(await request.body())
        inputs = InternshipRequest(payload, _school_periods(db))
        result = inputs.calculate()
    except (ValueError, TypeError, AttributeError) as exc:
        return JSONResponse({"ok": False, "error": _error_message(exc)}, status_code=status.HTTP_400_BAD_REQUEST)
    return JSONResponse(_serialize_result(result, _coverage_warning(db, result)))


@router.post("/export")
async def export_internship(request: Request, db: Session = Depends(get_db)):
    """Validate the payload again and stream the XLSX workbook."""

    form = await request.form()
    payload = None
    try:
        payload = json.loads(str(form.get("payload") or ""))
        inputs = InternshipRequest(payload, _school_periods(db))
        result = inputs.calculate()
    except (ValueError, TypeError, AttributeError) as exc:
        state = payload if isinstance(payload, dict) else None
        return _render_page(request, db, state=state, error=_error_message(exc), status_code=status.HTTP_400_BAD_REQUEST)

    non_working_dates, labels_by_date = inputs.non_working()
    workbook = build_internship_workbook(
        result,
        metadata=inputs.metadata,
        weekday_minutes=inputs.weekday_minutes,
        applied_periods=inputs.applied_periods(result),
        non_working_dates=non_working_dates,
        labels_by_date=labels_by_date,
    )
    return StreamingResponse(
        workbook,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{_export_filename(inputs.metadata)}"'},
    )
