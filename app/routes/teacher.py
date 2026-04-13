"""Routes for the public teacher planning workflow."""

import json
from datetime import date

from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import StreamingResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.date_utils import format_display_date, parse_date_input
from app.models import AcademicYearSetting, ExcludedPeriod
from app.services.allocation import BlockPlan, RAPlan, allocate_ra_hours, allocate_ra_hours_by_blocks, validate_ra_distribution
from app.services.calendar import ScheduleDay, build_schedule, expand_excluded_periods, total_available_hours
from app.services.export import build_workbook


router = APIRouter(tags=["teacher"])
templates = Jinja2Templates(directory="app/templates")
templates.env.filters["date_display"] = format_display_date
PLANNING_MODE_CHOICES = {"sequential", "parallel"}


def _parse_weekday_hours(form_data: dict[str, str]) -> dict[int, int]:
    """Convert the weekday hour inputs into a predictable Monday-Friday map."""

    values: dict[int, int] = {}
    for index, field_name in enumerate(["monday_hours", "tuesday_hours", "wednesday_hours", "thursday_hours", "friday_hours"]):
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


def _parse_block_weekday_hours(form_data: dict[str, str], prefix: str) -> dict[int, int]:
    """Convert one block's weekday inputs into a Monday-Friday map."""

    values: dict[int, int] = {}
    for index, field_name in enumerate(["monday_hours", "tuesday_hours", "wednesday_hours", "thursday_hours", "friday_hours"]):
        value = int(form_data.get(f"{prefix}_{field_name}", "0"))
        if value < 0 or value > 6:
            raise ValueError("Les hores dels blocs han d'estar entre 0 i 6.")
        values[index] = value
    return values


def _build_block_plans(form_data: dict[str, str], weekday_hours: dict[int, int], planning_mode: str) -> list[BlockPlan]:
    """Build the planning blocks for the advanced parallel mode."""

    if planning_mode != "parallel":
        return []

    block_1_hours = _parse_block_weekday_hours(form_data, "block_1")
    block_2_hours = _parse_block_weekday_hours(form_data, "block_2")
    for index in range(5):
        if block_1_hours[index] + block_2_hours[index] != weekday_hours[index]:
            raise ValueError("En mode per blocs, la suma dels blocs ha de coincidir amb les hores del calendari cada dia.")

    return [
        BlockPlan(key="block_1", name="Bloc 1", weekday_hours=block_1_hours),
        BlockPlan(key="block_2", name="Bloc 2", weekday_hours=block_2_hours),
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


def _summarize_exclusion_impact(
    start_date: date,
    end_date: date,
    weekday_hours: dict[int, int],
    excluded_dates: set[date],
) -> tuple[int, int]:
    """Return excluded teaching days and hours within the selected plan window."""

    excluded_teaching_days = 0
    excluded_teaching_hours = 0
    for current_date in excluded_dates:
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
    return excluded_teaching_days, excluded_teaching_hours


def _serialize_blocks(blocks: list[BlockPlan]) -> list[dict[str, object]]:
    """Convert block plans into JSON-safe dictionaries for the browser."""

    serialized_blocks: list[dict[str, object]] = []
    for block in blocks:
        serialized_blocks.append(
            {
                "key": block.key,
                "name": block.name,
                "weekday_hours": block.weekday_hours,
                "weekday_hours_display": _format_weekday_hours(block.weekday_hours),
            }
        )
    return serialized_blocks


def _summarize_block_available_hours(schedule: list[ScheduleDay], blocks: list[BlockPlan]) -> dict[str, int]:
    """Calculate how many schedule hours each block owns before any releases."""

    totals = {block.key: 0 for block in blocks}
    for day in schedule:
        for block in blocks:
            totals[block.key] += block.weekday_hours.get(day.weekday_index, 0)
    return totals


def _default_ra_state(ra_count: int, planning_mode: str) -> dict[str, object]:
    """Prepare the browser state used to render the RA editor."""

    order = [f"RA{index}" for index in range(1, ra_count + 1)]
    names = {key: key for key in order}
    hours = {key: 0 for key in order}
    if planning_mode == "parallel":
        blocks = {key: "block_1" if index == 0 else "block_2" for index, key in enumerate(order)}
    else:
        blocks = {}
    return {"order": order, "names": names, "hours": hours, "blocks": blocks}


def _format_blocks_summary(blocks: list[dict[str, object]], ra_order: list[str], ra_names: dict[str, str], ra_blocks: dict[str, str]) -> str:
    """Render a readable summary of the configured parallel blocks."""

    parts: list[str] = []
    for block in blocks:
        block_key = str(block["key"])
        block_ras = [ra_names[key].strip() or key for key in ra_order if ra_blocks.get(key) == block_key]
        ra_text = ", ".join(block_ras) if block_ras else "-"
        parts.append(f"{block['name']} ({block['weekday_hours_display']}): {ra_text}")
    return " | ".join(parts)


@router.get("/")
def index(request: Request, db: Session = Depends(get_db)):
    """Render the first planning step with default academic-year dates."""

    settings = db.get(AcademicYearSetting, 1)
    form = {
        "planning_mode": "sequential",
    }
    return templates.TemplateResponse(
        request,
        "teacher/index.html",
        {"settings": settings, "error": None, "form": form},
    )


@router.post("/plan")
async def prepare_plan(request: Request, db: Session = Depends(get_db)):
    """Validate teacher inputs and calculate the available teaching calendar."""

    form = await request.form()
    form_data = dict(form)
    settings = db.get(AcademicYearSetting, 1)

    try:
        start_date = parse_date_input(form_data["start_date"])
        end_date = parse_date_input(form_data["end_date"])
        if end_date < start_date:
            raise ValueError("La data de fi no pot ser anterior a la data d'inici.")
        weekday_hours = _parse_weekday_hours(form_data)
        planning_mode = _parse_planning_mode(form_data)
        blocks = _build_block_plans(form_data, weekday_hours, planning_mode)
        ra_count = int(form_data["ra_count"])
        if ra_count < 1 or ra_count > 12:
            raise ValueError("El nombre de RAs ha d'estar entre 1 i 12.")
    except (KeyError, ValueError) as exc:
        return templates.TemplateResponse(
            request,
            "teacher/index.html",
            {"settings": settings, "error": str(exc), "form": form_data},
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    periods = db.scalars(select(ExcludedPeriod)).all()
    # Admin exclusions are stored as ranges; they are expanded into concrete dates
    # so the teaching calendar can remove each blocked day precisely.
    excluded_dates = expand_excluded_periods([(period.start_date, period.end_date) for period in periods])
    schedule = build_schedule(start_date, end_date, weekday_hours, excluded_dates)
    total_hours = total_available_hours(schedule)
    block_available_hours = _summarize_block_available_hours(schedule, blocks)
    excluded_teaching_days, excluded_teaching_hours = _summarize_exclusion_impact(
        start_date, end_date, weekday_hours, excluded_dates
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

    # The second step runs in the browser, so we send a compact JSON payload that
    # contains everything needed to finish the RA distribution and export.
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
        "schedule": [
            {"date": day.date.isoformat(), "weekday_index": day.weekday_index, "weekday_name": day.weekday_name, "hours": day.hours}
            for day in schedule
        ],
        "total_available_hours": total_hours,
    }
    plan_payload["weekday_hours_display"] = _format_weekday_hours(plan_payload["weekday_hours"])
    for block in plan_payload["blocks"]:
        block["available_hours"] = block_available_hours.get(block["key"], 0)
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
    ra_blocks = json.loads(form.get("ra_blocks", "{}"))

    # Rebuild typed schedule objects from the JSON payload generated in step 1.
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
            weekday_hours={int(index): int(hours) for index, hours in item["weekday_hours"].items()},
        )
        for item in plan_data.get("blocks", [])
    ]
    ras = [
        RAPlan(
            key=ra_key,
            name=ra_names[ra_key].strip() or ra_key,
            hours=int(ra_hours[ra_key]),
            block_key=ra_blocks.get(ra_key) if plan_data.get("planning_mode") == "parallel" else None,
        )
        for ra_key in ra_order
    ]
    try:
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
                    {"order": ra_order, "names": ra_names, "hours": ra_hours, "blocks": ra_blocks}
                ),
                "export_error": str(exc),
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    # Allocation is done server-side again to avoid trusting browser calculations
    # for the final exported file.
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
        "Hores per RA": ", ".join(f"{ra.name}: {ra.hours}" for ra in ras),
        "Hores per dia": plan_data.get("weekday_hours_display") or _format_weekday_hours(plan_data["weekday_hours"]),
        "Impacte dels períodes sense classe": (
            f"{plan_data['excluded_teaching_days']} dies lectius, {plan_data['excluded_teaching_hours']} h"
        ),
    }
    if plan_data.get("planning_mode") == "parallel":
        summary["Blocs"] = _format_blocks_summary(plan_data.get("blocks", []), ra_order, ra_names, ra_blocks)
    workbook = build_workbook(rows, ras, summary)
    filename = f"{plan_data['subject_code'] or 'planificacio'}-calendari.xlsx"
    return StreamingResponse(
        workbook,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
