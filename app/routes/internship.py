"""Routes for the internship calendar planner.

The page recalculates live through `/practiques/calcul` (JSON), downloads
the workbook through `/practiques/export` and read-only copies through
`/practiques/export-html` and `/practiques/export-pdf`. All of them receive
the same JSON payload and run the same validation, so the exported files
always match the preview.
"""

from __future__ import annotations

import json
import re
import unicodedata
from datetime import date

from fastapi import APIRouter, Depends, Request, status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse, RedirectResponse, Response, StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.date_utils import format_display_date, parse_date_input
from app.models import AcademicYear, ExcludedPeriod
from app.routes.teacher import templates
from app.services.academic_years import get_active_academic_year
from app.services.calendar import daterange
from app.services.hours import BLOCK_MINUTE_CHOICES, MINUTES_PER_HOUR, format_minutes_label
from app.services.internship import DAY_KIND_OVERRIDE, MAX_DAILY_HOURS, InternshipCalendar, InternshipSchedule, build_internship_calendar
from app.services.internship_export import METADATA_FIELDS, build_internship_workbook, calendar_grid_end, schedule_sections
from app.services.internship_html import (
    CALENDAR_KIND_LABELS,
    WEEKDAY_SHORT,
    build_month_views,
    has_schedule_starts,
    inline_logo,
    inline_stylesheet,
    pdf_stylesheet,
    render_pdf,
)
from app.services.usage import INTERNSHIP_EXPORT, INTERNSHIP_EXPORT_HTML, INTERNSHIP_EXPORT_PDF, INTERNSHIP_VIEW, record_usage


router = APIRouter(prefix="/practiques", tags=["internship"])

MAX_TARGET_HOURS = 3000
MAX_EXTRA_PERIODS = 100
MAX_SCHEDULE_CHANGES = 20
WEEKDAY_LABELS = ("Dilluns", "Dimarts", "Dimecres", "Dijous", "Divendres")
MAX_LABEL_LENGTH = 120
MAX_METADATA_LENGTH = 200
METADATA_KEYS = tuple(key for key, _ in METADATA_FIELDS)
# Header columns of the HTML and PDF exports: student, then company and its
# tutor. The dates follow as a last column; empty fields and columns are left out.
DETAIL_COLUMNS = (
    ("student_name", "training_cycle", "group_name"),
    ("company_name", "company_tutor", "company_tutor_email"),
)
# Inputs embedded in the HTML export so it can be opened again in the planner.
PLAN_KEYS = (
    "start_date",
    "target_hours",
    "target_minutes",
    "weekday_minutes",
    "schedule_changes",
    "excluded_period_ids",
    "extra_periods",
    "overrides",
    "metadata",
)


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


def _parse_weekdays(raw: object, *, label_prefix: str = "") -> dict[int, int]:
    """Validate Monday-to-Friday minutes sent as {"0": minutes, ...}."""

    if not isinstance(raw, dict):
        raise ValueError("Horari setmanal no vàlid.")
    return {
        index: _parse_minutes(raw.get(str(index)), max_hours=MAX_DAILY_HOURS, field_label=f"{label_prefix}{label}")
        for index, label in enumerate(WEEKDAY_LABELS)
    }


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

        # The agreement's first schedule applies from the start date; each
        # change replaces it from its own date until the next change.
        self.weekday_minutes = _parse_weekdays(payload.get("weekday_minutes") or {})
        raw_changes = payload.get("schedule_changes") or []
        if len(raw_changes) > MAX_SCHEDULE_CHANGES:
            raise ValueError("Hi ha massa canvis d'horari.")
        changes: dict[date, dict[int, int]] = {}
        for item in raw_changes:
            change_start = parse_date_input(str(item.get("start") or ""))
            display = format_display_date(change_start)
            if change_start <= self.start_date:
                raise ValueError(f"L'horari que comença el {display} ha de començar després de la data d'inici de les pràctiques.")
            if change_start in changes:
                raise ValueError(f"Hi ha dos horaris que comencen el {display}.")
            changes[change_start] = _parse_weekdays(item.get("weekday_minutes") or {}, label_prefix=f"Horari del {display}, ")
        self.schedule = InternshipSchedule(self.weekday_minutes, list(changes.items()))

        try:
            selected_ids = {int(value) for value in payload.get("excluded_period_ids") or []}
        except (TypeError, ValueError):
            raise ValueError("Selecció de períodes no lectius no vàlida.") from None
        self.school_periods = [period for period in periods if period.id in selected_ids]

        raw_extra = payload.get("extra_periods") or []
        if len(raw_extra) > MAX_EXTRA_PERIODS:
            raise ValueError("Hi ha massa dies sense pràctiques afegits.")
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
            self.schedule,
            dates,
            self.overrides,
            labels,
        )

    def applied_periods(self, result: InternshipCalendar, until: date | None = None) -> list[dict[str, str]]:
        """Describe the periods that overlap the exported calendar.

        The workbook's grid runs past the end date (the default); the HTML
        copy passes the end date itself because it shows no further days.
        """

        grid_end = until or calendar_grid_end(result)
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
            "Afegeix aquí els festius posteriors."
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
        "complete": result.is_complete,
        "pending_display": format_minutes_label(result.pending_minutes),
        "deadline_display": format_display_date(result.deadline),
        "last_working_display": format_display_date(result.last_working_date) if result.last_working_date else None,
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
                "schedule": day.schedule_index,
            }
            for day in result.days
        ],
    }


def _export_filename(metadata: dict[str, str], extension: str = "xlsx") -> str:
    """Build an ASCII-safe filename, adding the student's name when present."""

    student = unicodedata.normalize("NFKD", metadata.get("student_name", "")).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^A-Za-z0-9]+", "-", student).strip("-").lower()
    return f"calendari-practiques-{slug}.{extension}" if slug else f"calendari-practiques.{extension}"


def _render_page(request: Request, db: Session, *, state: dict | None = None, error: str | None = None, status_code: int = 200):
    active_year = get_active_academic_year(db)
    periods = _school_periods(db)
    default_state = {
        "start_date": format_display_date(date.today()),
        "target_hours": "",
        "target_minutes": 0,
        "weekday_minutes": {str(index): 0 for index in range(5)},
        "schedule_changes": [],
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
            "calendar_kind_labels": CALENDAR_KIND_LABELS,
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

    record_usage(db, request, INTERNSHIP_VIEW)
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


async def _read_export_form(request: Request, db: Session):
    """Validate an export form's payload; return (payload, inputs, result) or an error page."""

    form = await request.form()
    payload = None
    try:
        payload = json.loads(str(form.get("payload") or ""))
        inputs = InternshipRequest(payload, _school_periods(db))
        result = inputs.calculate()
    except (ValueError, TypeError, AttributeError) as exc:
        state = payload if isinstance(payload, dict) else None
        return _render_page(request, db, state=state, error=_error_message(exc), status_code=status.HTTP_400_BAD_REQUEST)
    return payload, inputs, result


@router.post("/export")
async def export_internship(request: Request, db: Session = Depends(get_db)):
    """Validate the payload again and stream the XLSX workbook."""

    parsed = await _read_export_form(request, db)
    if not isinstance(parsed, tuple):
        return parsed
    _, inputs, result = parsed

    non_working_dates, labels_by_date = inputs.non_working()
    workbook = build_internship_workbook(
        result,
        metadata=inputs.metadata,
        schedule=inputs.schedule,
        applied_periods=inputs.applied_periods(result),
        non_working_dates=non_working_dates,
        labels_by_date=labels_by_date,
    )
    record_usage(db, request, INTERNSHIP_EXPORT)
    return StreamingResponse(
        workbook,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{_export_filename(inputs.metadata)}"'},
    )


def _detail_columns(metadata: dict[str, str], result: InternshipCalendar, summary: dict) -> list[list[tuple[str, str]]]:
    labels = dict(METADATA_FIELDS)
    columns = [[(labels[key], metadata[key]) for key in keys if metadata.get(key)] for keys in DETAIL_COLUMNS]
    columns.append([("Data d'inici", format_display_date(result.start_date)), ("Hores totals", summary["target_display"])])
    return [column for column in columns if column]


def _snapshot_context(payload: dict, inputs: InternshipRequest, result: InternshipCalendar, *, pdf: bool = False) -> dict:
    """Context for `internship/export.html`, shared by the HTML and PDF copies."""

    summary = _serialize_result(result, None)
    return {
        "pdf": pdf,
        "stylesheet": inline_stylesheet(),
        "pdf_stylesheet": pdf_stylesheet() if pdf else "",
        "logo": inline_logo(),
        "student_name": inputs.metadata.get("student_name", ""),
        "detail_columns": _detail_columns(inputs.metadata, result, summary),
        "summary": summary,
        "override_count": sum(1 for day in result.days if day.kind == DAY_KIND_OVERRIDE),
        "calendar_kind_labels": CALENDAR_KIND_LABELS,
        "show_schedule_start": has_schedule_starts(result),
        "months": build_month_views(result),
        "weekday_labels": WEEKDAY_LABELS,
        "weekday_short": WEEKDAY_SHORT,
        "schedules": [
            (title, [format_minutes_label(minutes[index]) if minutes.get(index) else "–" for index in range(5)],
             format_minutes_label(sum(minutes.values())))
            for title, minutes in schedule_sections(result, inputs.schedule)
        ],
        "periods": inputs.applied_periods(result, until=result.end_date),
        "generated_display": format_display_date(date.today()),
        "plan": {
            "format": "tempo.internship",
            "version": 1,
            "saved": date.today().isoformat(),
            "plan": {key: payload.get(key) for key in PLAN_KEYS},
            # Lets the planner warn on import if the school calendar has changed since.
            "result": {"end_date": result.end_date.isoformat(), "scheduled_minutes": result.scheduled_minutes},
        },
    }


@router.get("/export-html")
def redirect_stray_html_export():
    return RedirectResponse(url="/practiques", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/export-html")
async def export_internship_html(request: Request, db: Session = Depends(get_db)):
    """Validate the payload again and download a self-contained, read-only HTML copy."""

    parsed = await _read_export_form(request, db)
    if not isinstance(parsed, tuple):
        return parsed
    payload, inputs, result = parsed

    record_usage(db, request, INTERNSHIP_EXPORT_HTML)
    return templates.TemplateResponse(
        request,
        "internship/export.html",
        _snapshot_context(payload, inputs, result),
        headers={"Content-Disposition": f'attachment; filename="{_export_filename(inputs.metadata, "html")}"'},
    )


@router.get("/export-pdf")
def redirect_stray_pdf_export():
    return RedirectResponse(url="/practiques", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/export-pdf")
async def export_internship_pdf(request: Request, db: Session = Depends(get_db)):
    """Validate the payload again and download the read-only copy as a PDF."""

    parsed = await _read_export_form(request, db)
    if not isinstance(parsed, tuple):
        return parsed
    payload, inputs, result = parsed

    html = templates.get_template("internship/export.html").render(_snapshot_context(payload, inputs, result, pdf=True))
    record_usage(db, request, INTERNSHIP_EXPORT_PDF)
    # Layout takes a few seconds; keep it off the event loop.
    pdf = await run_in_threadpool(render_pdf, html)
    return Response(
        pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{_export_filename(inputs.metadata, "pdf")}"'},
    )
