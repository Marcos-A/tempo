"""Routes for the public teacher planning workflow."""

import json
from datetime import date

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.date_utils import format_display_date, parse_date_input
from app.models import AcademicWeekNumber, ExcludedPeriod
from app.services.academic_weeks import week_number_for_date
from app.services.allocation import BlockPlan, RAPlan, allocate_ra_hours, allocate_ra_hours_by_blocks, validate_ra_distribution
from app.services.academic_years import get_active_academic_year
from app.services.calendar import ScheduleDay, build_schedule, expand_excluded_periods, total_available_hours
from app.services.export import build_workbook
from app.services.hours import BLOCK_MINUTE_CHOICES, MINUTES_PER_HOUR, format_minutes_label, minutes_to_hour_number, parse_hour_minute_pair


router = APIRouter(tags=["teacher"])
templates = Jinja2Templates(directory="app/templates")
templates.env.filters["date_display"] = format_display_date
settings = get_settings()
templates.env.globals["app_name"] = settings.app_name
templates.env.globals["school_name"] = settings.school_name
templates.env.globals["block_minute_choices"] = BLOCK_MINUTE_CHOICES
PLANNING_MODE_CHOICES = {"sequential", "parallel"}
MAX_RA_COUNT = 24
WEEKDAY_FIELDS = ["monday", "tuesday", "wednesday", "thursday", "friday"]


def _parse_weekday_hours(form_data: dict[str, str]) -> dict[int, int]:
    """Convert the weekday hour inputs into a predictable Monday-Friday map."""

    values: dict[int, int] = {}
    for index, field_name in enumerate([f"{weekday}_hours" for weekday in WEEKDAY_FIELDS]):
        value = int(form_data.get(field_name, "0"))
        if value < 0 or value > 6:
            raise ValueError("Les hores per dia han d'estar entre 0 i 6.")
        values[index] = value
    return values


def _parse_planning_mode(form_data: dict[str, str]) -> str:
    """Read the requested planning mode, defaulting to sequential."""

    planning_mode = form_data.get("planning_mode", "sequential")
    if planning_mode not in PLANNING_MODE_CHOICES:
        raise ValueError("El mode de planificació seleccionat no és vàlid.")
    return planning_mode


def _validate_ra_count(form_data: dict[str, str], planning_mode: str) -> int:
    """Validate the requested RA count, including mode-specific constraints."""

    ra_count = int(form_data["ra_count"])
    if ra_count < 1 or ra_count > MAX_RA_COUNT:
        raise ValueError(f"El nombre de RAs ha d'estar entre 1 i {MAX_RA_COUNT}.")
    if planning_mode == "parallel" and ra_count == 1:
        raise ValueError("El mode per blocs en paral·lel requereix com a mínim 2 RAs.")
    return ra_count


def _parse_block_weekday_minutes(form_data: dict[str, str], prefix: str) -> dict[int, int]:
    """Convert one block's weekday inputs into exact minutes."""

    values: dict[int, int] = {}
    for index, weekday in enumerate(WEEKDAY_FIELDS):
        values[index] = parse_hour_minute_pair(
            form_data.get(f"{prefix}_{weekday}_hours", "0"),
            form_data.get(f"{prefix}_{weekday}_minutes", "0"),
        )
    return values


def _build_block_plans(form_data: dict[str, str], weekday_hours: dict[int, int], planning_mode: str) -> list[BlockPlan]:
    """Build the planning blocks for the advanced parallel mode."""

    if planning_mode != "parallel":
        return []

    block_1_minutes = _parse_block_weekday_minutes(form_data, "block_1")
    block_2_minutes = _parse_block_weekday_minutes(form_data, "block_2")
    for index in range(5):
        weekday_total_minutes = weekday_hours[index] * MINUTES_PER_HOUR
        if block_1_minutes[index] > weekday_total_minutes or block_2_minutes[index] > weekday_total_minutes:
            raise ValueError("Cap bloc pot superar les hores del calendari assignades a aquell dia.")
        if block_1_minutes[index] + block_2_minutes[index] != weekday_total_minutes:
            raise ValueError("En mode per blocs, la suma dels blocs ha de coincidir amb les hores del calendari cada dia.")

    return [
        BlockPlan(key="block_1", name="Bloc 1", weekday_minutes=block_1_minutes),
        BlockPlan(key="block_2", name="Bloc 2", weekday_minutes=block_2_minutes),
    ]


def _format_weekday_hours(weekday_hours: dict[int | str, int | str]) -> str:
    """Return assigned weekday hours using compact Catalan abbreviations."""

    labels = ("dl.", "dt.", "dc.", "dj.", "dv.")
    parts: list[str] = []
    for index, label in enumerate(labels):
        hours = int(weekday_hours.get(index, weekday_hours.get(str(index), 0)))
        if hours >= 1:
            parts.append(f"{label}: {hours}")
    return ", ".join(parts) if parts else "-"


def _format_weekday_minutes(weekday_minutes: dict[int | str, int | str]) -> str:
    """Return assigned weekday block times using compact Catalan abbreviations."""

    labels = ("dl.", "dt.", "dc.", "dj.", "dv.")
    parts: list[str] = []
    for index, label in enumerate(labels):
        minutes = int(weekday_minutes.get(index, weekday_minutes.get(str(index), 0)))
        if minutes > 0:
            parts.append(f"{label}: {format_minutes_label(minutes)}")
    return ", ".join(parts) if parts else "-"


def _summarize_exclusion_impact(
    start_date: date,
    end_date: date,
    weekday_hours: dict[int, int],
    excluded_dates: set[date],
    excluded_labels_by_date: dict[date, str],
) -> tuple[int, int, list[dict[str, object]]]:
    """Return excluded teaching days, hours, and affected dates within the plan window."""

    excluded_teaching_days = 0
    excluded_teaching_hours = 0
    affected_dates: list[dict[str, object]] = []
    weekday_labels = ("dl.", "dt.", "dc.", "dj.", "dv.")
    for current_date in sorted(excluded_dates):
        if not (start_date <= current_date <= end_date):
            continue
        weekday_index = current_date.weekday()
        if weekday_index > 4:
            continue
        hours = weekday_hours.get(weekday_index, 0)
        if hours <= 0:
            continue
        excluded_teaching_days += 1
        excluded_teaching_hours += hours
        label = excluded_labels_by_date.get(current_date, "").strip()
        label_text = f" ({label})" if label else ""
        affected_dates.append(
            {
                "date": current_date.isoformat(),
                "display": f"{weekday_labels[weekday_index]} {format_display_date(current_date)}{label_text}",
                "hours": hours,
                "hours_display": f"{hours} h",
                "label": label,
            }
        )
    return excluded_teaching_days, excluded_teaching_hours, affected_dates


def _serialize_blocks(blocks: list[BlockPlan]) -> list[dict[str, object]]:
    """Convert block plans into JSON-safe dictionaries for the browser."""

    serialized_blocks: list[dict[str, object]] = []
    for block in blocks:
        serialized_blocks.append(
            {
                "key": block.key,
                "name": block.name,
                "weekday_minutes": block.weekday_minutes,
                "weekday_hours_display": _format_weekday_minutes(block.weekday_minutes),
            }
        )
    return serialized_blocks


def _summarize_block_available_minutes(schedule: list[ScheduleDay], blocks: list[BlockPlan]) -> dict[str, int]:
    """Calculate how many schedule minutes each block owns before any releases."""

    totals = {block.key: 0 for block in blocks}
    for day in schedule:
        for block in blocks:
            totals[block.key] += block.weekday_minutes.get(day.weekday_index, 0)
    return totals


def _map_excluded_labels_by_date(periods: list[ExcludedPeriod]) -> dict[date, str]:
    """Map excluded dates to their optional labels for user-facing summaries."""

    labels_by_date: dict[date, str] = {}
    for period in periods:
        label = (period.label or "").strip()
        current_date = period.start_date
        while current_date <= period.end_date:
            if label and current_date not in labels_by_date:
                labels_by_date[current_date] = label
            current_date = current_date.fromordinal(current_date.toordinal() + 1)
    return labels_by_date


def _week_numbers_for_schedule(db: Session, academic_year_id: int, schedule: list[ScheduleDay]) -> dict[str, int]:
    """Map each schedule date (ISO string) to its admin-assigned week number.

    Only dates whose week actually has a saved number are included, so
    unassigned weeks stay blank instead of surfacing a stray zero or null.
    """

    saved_numbers = {
        row.week_start_date: row.number
        for row in db.scalars(select(AcademicWeekNumber).where(AcademicWeekNumber.academic_year_id == academic_year_id)).all()
    }
    week_numbers: dict[str, int] = {}
    for day in schedule:
        number = week_number_for_date(day.date, saved_numbers)
        if number is not None:
            week_numbers[day.date.isoformat()] = number
    return week_numbers


def _default_ra_state(ra_count: int, planning_mode: str) -> dict[str, object]:
    """Prepare the browser state used to render the RA editor."""

    order = [f"RA{index}" for index in range(1, ra_count + 1)]
    names = {key: key for key in order}
    hours = {key: 0 for key in order}
    minutes = {key: 0 for key in order}
    if planning_mode == "parallel":
        blocks = {key: "block_1" if index == 0 else "block_2" for index, key in enumerate(order)}
    else:
        blocks = {}
    return {"order": order, "names": names, "hours": hours, "minutes": minutes, "blocks": blocks}


def _format_blocks_summary(blocks: list[dict[str, object]], ra_order: list[str], ra_names: dict[str, str], ra_blocks: dict[str, str]) -> str:
    """Render a readable summary of the configured parallel blocks."""

    parts: list[str] = []
    for block in blocks:
        block_key = str(block["key"])
        block_ras = [ra_names[key].strip() or key for key in ra_order if ra_blocks.get(key) == block_key]
        ra_text = ", ".join(block_ras) if block_ras else "-"
        parts.append(f"{block['name']} ({block['weekday_hours_display']}): {ra_text}")
    return " | ".join(parts)


STRAY_ENTRY_NOTICE = "Comença una planificació nova des d'aquí."


@router.get("/")
def index(request: Request, db: Session = Depends(get_db)):
    """Render the first planning step with default academic-year dates."""

    settings = get_active_academic_year(db)
    form = {
        "planning_mode": "sequential",
    }
    notice = STRAY_ENTRY_NOTICE if request.query_params.get("notice") == "start-here" else None
    return templates.TemplateResponse(
        request,
        "teacher/index.html",
        {"settings": settings, "error": None, "notice": notice, "form": form},
    )


@router.get("/plan")
@router.get("/export")
def redirect_stray_step_access():
    """Send direct visits to the step-2/export URLs back to the start of the flow.

    Both routes only accept POST with data produced by the previous step, so a
    bookmark, page refresh, or shared link that hits them with a plain GET
    would otherwise surface a raw "Method Not Allowed" response.
    """

    return RedirectResponse(url="/?notice=start-here", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/plan")
async def prepare_plan(request: Request, db: Session = Depends(get_db)):
    """Validate teacher inputs and calculate the available teaching calendar."""

    form = await request.form()
    form_data = dict(form)
    settings = get_active_academic_year(db)

    try:
        start_date = parse_date_input(form_data["start_date"])
        end_date = parse_date_input(form_data["end_date"])
        if end_date < start_date:
            raise ValueError("La data de fi no pot ser anterior a la data d'inici.")
        weekday_hours = _parse_weekday_hours(form_data)
        planning_mode = _parse_planning_mode(form_data)
        blocks = _build_block_plans(form_data, weekday_hours, planning_mode)
        ra_count = _validate_ra_count(form_data, planning_mode)
    except (KeyError, ValueError) as exc:
        return templates.TemplateResponse(
            request,
            "teacher/index.html",
            {"settings": settings, "error": str(exc), "form": form_data},
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    periods = db.scalars(select(ExcludedPeriod).where(ExcludedPeriod.academic_year_id == settings.id)).all()
    excluded_dates = expand_excluded_periods([(period.start_date, period.end_date) for period in periods])
    excluded_labels_by_date = _map_excluded_labels_by_date(periods)
    schedule = build_schedule(start_date, end_date, weekday_hours, excluded_dates)
    total_hours = total_available_hours(schedule)
    block_available_minutes = _summarize_block_available_minutes(schedule, blocks)
    excluded_teaching_days, excluded_teaching_hours, excluded_teaching_dates = _summarize_exclusion_impact(
        start_date, end_date, weekday_hours, excluded_dates, excluded_labels_by_date
    )

    if total_hours == 0:
        return templates.TemplateResponse(
            request,
            "teacher/index.html",
            {
                "settings": settings,
                "error": "L'interval seleccionat i l'horari indiquen zero hores lectives disponibles.",
                "form": form_data,
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    # Week numbers come from the school's official academic-year calendar, so
    # they only make sense when the teacher is planning against that exact
    # window, and only when the admin has opted in on /admin/weeks. A custom
    # start/end date has no guaranteed relationship to the school's published
    # week numbering, so the column is left out entirely regardless of the toggle.
    include_week_numbers = (
        settings.include_week_numbers_in_export
        and start_date == settings.default_start_date
        and end_date == settings.default_end_date
    )
    week_numbers_by_date = _week_numbers_for_schedule(db, settings.id, schedule) if include_week_numbers else {}

    plan_payload = {
        "training_cycle": form_data.get("training_cycle", "").strip(),
        "group_name": form_data.get("group_name", "").strip(),
        "subject_code": form_data.get("subject_code", "").strip(),
        "subject_name": form_data.get("subject_name", "").strip(),
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "start_date_display": format_display_date(start_date),
        "end_date_display": format_display_date(end_date),
        "weekday_hours": weekday_hours,
        "planning_mode": planning_mode,
        "planning_mode_label": "Per blocs en paral·lel" if planning_mode == "parallel" else "Seqüencial",
        "blocks": _serialize_blocks(blocks),
        "ra_count": ra_count,
        "excluded_teaching_days": excluded_teaching_days,
        "excluded_teaching_hours": excluded_teaching_hours,
        "excluded_teaching_dates": excluded_teaching_dates,
        "include_week_numbers": include_week_numbers,
        "schedule": [
            {
                "date": day.date.isoformat(),
                "weekday_index": day.weekday_index,
                "weekday_name": day.weekday_name,
                "hours": day.hours,
                "week_number": week_numbers_by_date.get(day.date.isoformat()),
            }
            for day in schedule
        ],
        "total_available_hours": total_hours,
        "total_available_minutes": total_hours * MINUTES_PER_HOUR,
        "total_available_display": format_minutes_label(total_hours * MINUTES_PER_HOUR) if planning_mode == "parallel" else f"{total_hours} h",
    }
    plan_payload["weekday_hours_display"] = _format_weekday_hours(plan_payload["weekday_hours"])
    for block in plan_payload["blocks"]:
        block["available_minutes"] = block_available_minutes.get(block["key"], 0)
        block["available_hours_display"] = format_minutes_label(block["available_minutes"])
    return templates.TemplateResponse(
        request,
        "teacher/distribution.html",
        {
            "summary": plan_payload,
            "plan_json": json.dumps(plan_payload),
            "ra_state_json": json.dumps(_default_ra_state(ra_count, planning_mode)),
        },
    )


@router.post("/export")
async def export_plan(request: Request):
    """Validate the final RA distribution and stream the XLSX workbook."""

    form = await request.form()
    plan_data = json.loads(form["plan_json"])
    ra_order = json.loads(form["ra_order"])
    ra_names = json.loads(form["ra_names"])
    ra_hours = json.loads(form["ra_hours"])
    ra_minutes = json.loads(form.get("ra_minutes", "{}"))
    ra_blocks = json.loads(form.get("ra_blocks", "{}"))

    schedule_days = [
        ScheduleDay(
            date=date.fromisoformat(item["date"]),
            weekday_index=item["weekday_index"],
            weekday_name=item["weekday_name"],
            hours=item["hours"],
        )
        for item in plan_data["schedule"]
    ]

    blocks = [
        BlockPlan(
            key=item["key"],
            name=item["name"],
            weekday_minutes={int(index): int(minutes) for index, minutes in item["weekday_minutes"].items()},
        )
        for item in plan_data.get("blocks", [])
    ]
    if plan_data.get("planning_mode") == "parallel":
        ras = [
            RAPlan(
                key=ra_key,
                name=ra_names[ra_key].strip() or ra_key,
                hours=minutes_to_hour_number(int(ra_minutes[ra_key])),
                minutes=int(ra_minutes[ra_key]),
                block_key=ra_blocks.get(ra_key),
            )
            for ra_key in ra_order
        ]
    else:
        ras = [
            RAPlan(
                key=ra_key,
                name=ra_names[ra_key].strip() or ra_key,
                hours=int(ra_hours[ra_key]),
                block_key=None,
            )
            for ra_key in ra_order
        ]
    try:
        if plan_data.get("planning_mode") == "parallel":
            validate_ra_distribution(int(plan_data["total_available_minutes"]), ras, use_minutes=True)
        else:
            validate_ra_distribution(int(plan_data["total_available_hours"]), ras)
        if plan_data.get("planning_mode") == "parallel" and any(not ra.block_key for ra in ras):
            raise ValueError("Assigna cada RA a un dels dos blocs abans d'exportar.")
        rows = (
            allocate_ra_hours_by_blocks(schedule_days, ras, blocks)
            if plan_data.get("planning_mode") == "parallel"
            else allocate_ra_hours(schedule_days, ras)
        )
    except ValueError as exc:
        return templates.TemplateResponse(
            request,
            "teacher/distribution.html",
            {
                "summary": plan_data,
                "plan_json": json.dumps(plan_data),
                "ra_state_json": json.dumps(
                    {"order": ra_order, "names": ra_names, "hours": ra_hours, "minutes": ra_minutes, "blocks": ra_blocks}
                ),
                "export_error": str(exc),
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    summary = {
        "Cicle formatiu": plan_data.get("training_cycle") or "-",
        "Grup": plan_data.get("group_name") or "-",
        "Codi del mòdul": plan_data["subject_code"] or "-",
        "Nom del mòdul": plan_data["subject_name"] or "-",
        "Data d'inici de la planificació": plan_data.get("start_date_display", plan_data["start_date"]),
        "Data de fi de la planificació": plan_data.get("end_date_display", plan_data["end_date"]),
        "Hores totals disponibles": plan_data["total_available_hours"],
        "Nombre de RAs": plan_data["ra_count"],
        "Mode de planificació": plan_data.get("planning_mode_label", "Seqüencial"),
        "Ordre de les RAs": ", ".join(ra_order),
        "Hores per RA": ", ".join(
            f"{ra.name}: {format_minutes_label(ra.minutes)}" if ra.minutes is not None else f"{ra.name}: {ra.hours}"
            for ra in ras
        ),
        "Hores per dia": plan_data.get("weekday_hours_display") or _format_weekday_hours(plan_data["weekday_hours"]),
        "Impacte dels períodes sense classe": (
            f"{plan_data['excluded_teaching_days']} dies lectius, {plan_data['excluded_teaching_hours']} h"
        ),
    }
    if plan_data.get("planning_mode") == "parallel":
        summary["Blocs"] = _format_blocks_summary(plan_data.get("blocks", []), ra_order, ra_names, ra_blocks)

    include_week_numbers = bool(plan_data.get("include_week_numbers"))
    if include_week_numbers:
        week_numbers_by_date = {
            date.fromisoformat(item["date"]): item.get("week_number") for item in plan_data["schedule"]
        }
        for row in rows:
            row["week_number"] = week_numbers_by_date.get(row["date"])

    workbook = build_workbook(rows, ras, summary, include_week_numbers=include_week_numbers)
    group_name = (plan_data.get('group_name') or '').strip()
    subject_code = (plan_data.get('subject_code') or '').strip()
    filename_stem = f"{group_name}-{subject_code}-temporitzacio" if group_name and subject_code else "temporitzacio"
    filename = f"{filename_stem}.xlsx"
    return StreamingResponse(
        workbook,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
