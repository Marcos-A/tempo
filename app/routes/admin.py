"""Routes for the protected admin area."""

from collections import Counter
from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import verify_password
from app.config import get_settings
from app.database import get_db
from app.date_utils import format_display_date, format_month_label, parse_date_input
from app.dependencies import require_admin
from app.models import AcademicWeekNumber, AcademicYear, AdminUser, ExcludedPeriod
from app.services.academic_weeks import is_vacation_week, iter_week_starts, suggest_week_numbers
from app.services.academic_years import activate_academic_year, find_overlapping_year, get_active_academic_year, list_academic_years, suggest_year_label
from app.services.calendar import expand_excluded_periods


router = APIRouter(prefix="/admin", tags=["admin"])
templates = Jinja2Templates(directory="app/templates")
templates.env.filters["date_display"] = format_display_date
settings = get_settings()
templates.env.globals["app_name"] = settings.app_name
templates.env.globals["school_name"] = settings.school_name
SELECTED_YEAR_SECTION_ID = "academic-year-detail"
EXCLUDED_PERIODS_SECTION_ID = "excluded-periods"
DANGER_ZONE_SECTION_ID = "danger-zone"
WEEK_FIELD_PREFIX = "week_"
STATUS_MESSAGES = {
    "year-created": ("Curs acadèmic creat.", "ok"),
    "year-updated": ("Curs acadèmic actualitzat.", "ok"),
    "year-activated": ("Aquest és ara el curs actiu per al professorat.", "ok"),
    "year-deleted": ("Curs acadèmic suprimit.", "ok"),
    "period-added": ("Període sense classe afegit.", "ok"),
    "period-updated": ("Període sense classe actualitzat.", "ok"),
    "period-deleted": ("Període sense classe suprimit.", "ok"),
    "weeks-updated": ("Numeració de setmanes desada.", "ok"),
}


def _status_from_request(request: Request) -> tuple[str | None, str | None]:
    """Resolve the optional banner message requested by the UI redirect."""

    status_name = request.query_params.get("status")
    return STATUS_MESSAGES.get(status_name, (None, None))


def _selected_year_from_request(request: Request, db: Session) -> AcademicYear:
    """Resolve the year selected in the UI, falling back to the active one."""

    year_id_raw = request.query_params.get("year_id")
    if year_id_raw and year_id_raw.isdigit():
        selected_year = db.get(AcademicYear, int(year_id_raw))
        if selected_year is not None:
            return selected_year
    return get_active_academic_year(db)


def _periods_for_year(db: Session, academic_year_id: int) -> list[ExcludedPeriod]:
    """Return excluded periods belonging to one academic year."""

    return db.scalars(
        select(ExcludedPeriod)
        .where(ExcludedPeriod.academic_year_id == academic_year_id)
        .order_by(ExcludedPeriod.start_date, ExcludedPeriod.end_date, ExcludedPeriod.id)
    ).all()


def _year_dashboard_url(year_id: int | None = None, *, status_name: str | None = None, section_id: str | None = None) -> str:
    """Build a stable redirect back to the admin dashboard."""

    params: list[str] = []
    if year_id is not None:
        params.append(f"year_id={year_id}")
    if status_name:
        params.append(f"status={status_name}")
    url = "/admin"
    if params:
        url += "?" + "&".join(params)
    if section_id:
        url += f"#{section_id}"
    return url


def _academic_year_rows(db: Session) -> tuple[AcademicYear, list[dict[str, object]], Counter[int], Counter[int]]:
    """Collect academic-year rows plus lightweight counts for the admin UI."""

    academic_years = list_academic_years(db)
    active_year = get_active_academic_year(db)
    period_counts = Counter(
        academic_year_id
        for academic_year_id in db.scalars(select(ExcludedPeriod.academic_year_id)).all()
        if academic_year_id is not None
    )
    week_counts = Counter(
        academic_year_id
        for academic_year_id in db.scalars(select(AcademicWeekNumber.academic_year_id)).all()
        if academic_year_id is not None
    )
    academic_year_rows = [
        {
            "year": academic_year,
            "period_count": period_counts.get(academic_year.id, 0),
            "week_count": week_counts.get(academic_year.id, 0),
        }
        for academic_year in academic_years
    ]
    return active_year, academic_year_rows, period_counts, week_counts


def _render_dashboard(
    request: Request,
    db: Session,
    *,
    selected_year: AcademicYear | None = None,
    error: str | None = None,
    focus_section: str | None = None,
    status_code: int = status.HTTP_200_OK,
    new_year_form: dict[str, str] | None = None,
):
    """Render the admin dashboard with active-year and detail context."""

    active_year, academic_year_rows, period_counts, week_counts = _academic_year_rows(db)
    if selected_year is None:
        selected_year = active_year

    status_message, status_tone = _status_from_request(request)

    periods = _periods_for_year(db, selected_year.id)
    return templates.TemplateResponse(
        request,
        "admin/dashboard.html",
        {
            "academic_year_rows": academic_year_rows,
            "active_year": active_year,
            "selected_year": selected_year,
            "periods": periods,
            "selected_period_count": period_counts.get(selected_year.id, 0),
            "selected_week_count": week_counts.get(selected_year.id, 0),
            "error": error,
            "focus_section": focus_section,
            "status_message": status_message,
            "status_tone": status_tone,
            "new_year_form": new_year_form or {"year_label": "", "default_start_date": "", "default_end_date": ""},
        },
        status_code=status_code,
    )


def _render_years_index(request: Request, db: Session, *, status_code: int = status.HTTP_200_OK):
    """Render the compact index of all academic years."""

    active_year, academic_year_rows, _, _ = _academic_year_rows(db)
    status_message, status_tone = _status_from_request(request)
    return templates.TemplateResponse(
        request,
        "admin/years.html",
        {
            "active_year": active_year,
            "academic_year_rows": academic_year_rows,
            "status_message": status_message,
            "status_tone": status_tone,
        },
        status_code=status_code,
    )


@router.get("/login")
def login_page(request: Request):
    """Render the admin login form."""

    return templates.TemplateResponse(request, "admin/login.html", {"error": None})


@router.post("/login")
def login(request: Request, username: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    """Authenticate the admin and store the user id in the session cookie."""

    user = db.scalar(select(AdminUser).where(AdminUser.username == username))
    if user is None or not verify_password(password, user.password_hash):
        return templates.TemplateResponse(
            request,
            "admin/login.html",
            {"error": "Credencials no vàlides."},
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    request.session["admin_user_id"] = user.id
    return RedirectResponse(url="/admin", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/logout")
def logout(request: Request):
    """Clear the session so the browser is no longer authenticated."""

    request.session.clear()
    return RedirectResponse(url="/admin/login", status_code=status.HTTP_303_SEE_OTHER)


@router.get("")
def admin_dashboard(request: Request, db: Session = Depends(get_db), _: AdminUser = Depends(require_admin)):
    """Show the active-year dashboard and selected year's detail view."""

    return _render_dashboard(request, db, selected_year=_selected_year_from_request(request, db))


@router.get("/years")
def years_index(request: Request, db: Session = Depends(get_db), _: AdminUser = Depends(require_admin)):
    """Show the compact index used to access less-frequent year management."""

    return _render_years_index(request, db)


@router.post("/years")
def create_year(
    request: Request,
    year_label_raw: str = Form("", alias="year_label"),
    default_start_date_raw: str = Form(..., alias="default_start_date"),
    default_end_date_raw: str = Form(..., alias="default_end_date"),
    db: Session = Depends(get_db),
    _: AdminUser = Depends(require_admin),
):
    """Create a new academic year kept separate from the active one."""

    new_year_form = {
        "year_label": year_label_raw,
        "default_start_date": default_start_date_raw,
        "default_end_date": default_end_date_raw,
    }
    try:
        default_start_date = parse_date_input(default_start_date_raw)
        default_end_date = parse_date_input(default_end_date_raw)
    except ValueError as exc:
        return _render_dashboard(
            request,
            db,
            selected_year=_selected_year_from_request(request, db),
            error=str(exc),
            focus_section=None,
            status_code=status.HTTP_400_BAD_REQUEST,
            new_year_form=new_year_form,
        )

    if default_end_date < default_start_date:
        return _render_dashboard(
            request,
            db,
            selected_year=_selected_year_from_request(request, db),
            error="La data de fi no pot ser anterior a la data d'inici.",
            status_code=status.HTTP_400_BAD_REQUEST,
            new_year_form=new_year_form,
        )

    overlapping_year = find_overlapping_year(db, default_start_date, default_end_date)
    if overlapping_year is not None:
        return _render_dashboard(
            request,
            db,
            selected_year=overlapping_year,
            error=f"Aquest interval se solapa amb el curs {overlapping_year.label}.",
            focus_section=SELECTED_YEAR_SECTION_ID,
            status_code=status.HTTP_400_BAD_REQUEST,
            new_year_form=new_year_form,
        )

    academic_year = AcademicYear(
        label=year_label_raw.strip() or suggest_year_label(default_start_date, default_end_date),
        default_start_date=default_start_date,
        default_end_date=default_end_date,
        include_week_numbers_in_export=False,
        is_active=False,
    )
    if db.scalar(select(AcademicYear.id).limit(1)) is None:
        academic_year.is_active = True
    db.add(academic_year)
    db.commit()
    return RedirectResponse(
        url=_year_dashboard_url(academic_year.id, status_name="year-created", section_id=SELECTED_YEAR_SECTION_ID),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/years/{year_id}")
def update_year(
    request: Request,
    year_id: int,
    year_label_raw: str = Form("", alias="year_label"),
    default_start_date_raw: str = Form(..., alias="default_start_date"),
    default_end_date_raw: str = Form(..., alias="default_end_date"),
    include_week_numbers_in_export: Annotated[bool, Form()] = False,
    db: Session = Depends(get_db),
    _: AdminUser = Depends(require_admin),
):
    """Update the selected academic year's main settings."""

    academic_year = db.get(AcademicYear, year_id)
    if academic_year is None:
        return RedirectResponse(url="/admin", status_code=status.HTTP_303_SEE_OTHER)

    try:
        default_start_date = parse_date_input(default_start_date_raw)
        default_end_date = parse_date_input(default_end_date_raw)
    except ValueError as exc:
        return _render_dashboard(
            request,
            db,
            selected_year=academic_year,
            error=str(exc),
            focus_section=SELECTED_YEAR_SECTION_ID,
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    if default_end_date < default_start_date:
        return _render_dashboard(
            request,
            db,
            selected_year=academic_year,
            error="La data de fi no pot ser anterior a la data d'inici.",
            focus_section=SELECTED_YEAR_SECTION_ID,
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    overlapping_year = find_overlapping_year(db, default_start_date, default_end_date, exclude_year_id=academic_year.id)
    if overlapping_year is not None:
        return _render_dashboard(
            request,
            db,
            selected_year=academic_year,
            error=f"Aquest interval se solapa amb el curs {overlapping_year.label}.",
            focus_section=SELECTED_YEAR_SECTION_ID,
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    academic_year.label = year_label_raw.strip() or suggest_year_label(default_start_date, default_end_date)
    academic_year.default_start_date = default_start_date
    academic_year.default_end_date = default_end_date
    academic_year.include_week_numbers_in_export = include_week_numbers_in_export
    db.commit()
    return RedirectResponse(
        url=_year_dashboard_url(academic_year.id, status_name="year-updated", section_id=SELECTED_YEAR_SECTION_ID),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/years/{year_id}/activate")
def activate_year(year_id: int, db: Session = Depends(get_db), _: AdminUser = Depends(require_admin)):
    """Switch the teacher-facing default year."""

    academic_year = db.get(AcademicYear, year_id)
    if academic_year is None:
        return RedirectResponse(url="/admin", status_code=status.HTTP_303_SEE_OTHER)

    activate_academic_year(db, academic_year)
    db.commit()
    return RedirectResponse(
        url=_year_dashboard_url(academic_year.id, status_name="year-activated", section_id=SELECTED_YEAR_SECTION_ID),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/years/{year_id}/delete")
def delete_year(
    request: Request,
    year_id: int,
    confirm_delete: Annotated[str | None, Form()] = None,
    db: Session = Depends(get_db),
    _: AdminUser = Depends(require_admin),
):
    """Delete one non-active academic year and all its dependent records."""

    academic_year = db.get(AcademicYear, year_id)
    if academic_year is None:
        return RedirectResponse(url="/admin", status_code=status.HTTP_303_SEE_OTHER)
    if academic_year.is_active:
        return _render_dashboard(
            request,
            db,
            selected_year=academic_year,
            error="Canvia primer el curs actiu abans de suprimir-lo.",
            focus_section=DANGER_ZONE_SECTION_ID,
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    if confirm_delete != "on":
        return _render_dashboard(
            request,
            db,
            selected_year=academic_year,
            error="Marca la confirmació abans de suprimir aquest curs.",
            focus_section=DANGER_ZONE_SECTION_ID,
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    for period in _periods_for_year(db, academic_year.id):
        db.delete(period)
    for week in db.scalars(select(AcademicWeekNumber).where(AcademicWeekNumber.academic_year_id == academic_year.id)).all():
        db.delete(week)
    db.delete(academic_year)
    db.commit()
    return RedirectResponse(url=_year_dashboard_url(status_name="year-deleted"), status_code=status.HTTP_303_SEE_OTHER)


@router.post("/years/{year_id}/periods")
def add_period(
    request: Request,
    year_id: int,
    start_date_raw: str = Form(..., alias="start_date"),
    end_date_raw: Annotated[str | None, Form(alias="end_date")] = None,
    label: Annotated[str | None, Form()] = None,
    db: Session = Depends(get_db),
    _: AdminUser = Depends(require_admin),
):
    """Store a no-class day or inclusive range for one academic year."""

    academic_year = db.get(AcademicYear, year_id)
    if academic_year is None:
        return RedirectResponse(url="/admin", status_code=status.HTTP_303_SEE_OTHER)

    try:
        start_date = parse_date_input(start_date_raw)
        end_date = start_date if not end_date_raw else parse_date_input(end_date_raw)
    except ValueError as exc:
        return _render_dashboard(
            request,
            db,
            selected_year=academic_year,
            error=str(exc),
            focus_section=EXCLUDED_PERIODS_SECTION_ID,
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    if end_date < start_date:
        return _render_dashboard(
            request,
            db,
            selected_year=academic_year,
            error="La data de fi no pot ser anterior a la data d'inici.",
            focus_section=EXCLUDED_PERIODS_SECTION_ID,
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    existing_period = db.scalar(
        select(ExcludedPeriod).where(
            ExcludedPeriod.academic_year_id == academic_year.id,
            ExcludedPeriod.start_date == start_date,
            ExcludedPeriod.end_date == end_date,
        )
    )
    if existing_period is not None:
        error_message = (
            "Aquesta data sense classe ja existeix en aquest curs."
            if start_date == end_date
            else "Aquest període sense classe ja existeix en aquest curs."
        )
        return _render_dashboard(
            request,
            db,
            selected_year=academic_year,
            error=error_message,
            focus_section=EXCLUDED_PERIODS_SECTION_ID,
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    db.add(
        ExcludedPeriod(
            academic_year_id=academic_year.id,
            start_date=start_date,
            end_date=end_date,
            label=(label or "").strip() or None,
        )
    )
    db.commit()
    return RedirectResponse(
        url=_year_dashboard_url(academic_year.id, status_name="period-added", section_id=EXCLUDED_PERIODS_SECTION_ID),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/years/{year_id}/periods/{period_id}")
def update_period(
    request: Request,
    year_id: int,
    period_id: int,
    start_date_raw: str = Form(..., alias="start_date"),
    end_date_raw: Annotated[str | None, Form(alias="end_date")] = None,
    label: Annotated[str | None, Form()] = None,
    db: Session = Depends(get_db),
    _: AdminUser = Depends(require_admin),
):
    """Edit one previously saved excluded period."""

    academic_year = db.get(AcademicYear, year_id)
    period = db.get(ExcludedPeriod, period_id)
    if academic_year is None or period is None or period.academic_year_id != academic_year.id:
        return RedirectResponse(url="/admin", status_code=status.HTTP_303_SEE_OTHER)

    try:
        start_date = parse_date_input(start_date_raw)
        end_date = start_date if not end_date_raw else parse_date_input(end_date_raw)
    except ValueError as exc:
        return _render_dashboard(
            request,
            db,
            selected_year=academic_year,
            error=str(exc),
            focus_section=EXCLUDED_PERIODS_SECTION_ID,
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    if end_date < start_date:
        return _render_dashboard(
            request,
            db,
            selected_year=academic_year,
            error="La data de fi no pot ser anterior a la data d'inici.",
            focus_section=EXCLUDED_PERIODS_SECTION_ID,
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    existing_period = db.scalar(
        select(ExcludedPeriod).where(
            ExcludedPeriod.academic_year_id == academic_year.id,
            ExcludedPeriod.start_date == start_date,
            ExcludedPeriod.end_date == end_date,
            ExcludedPeriod.id != period_id,
        )
    )
    if existing_period is not None:
        error_message = (
            "Aquesta data sense classe ja existeix en aquest curs."
            if start_date == end_date
            else "Aquest període sense classe ja existeix en aquest curs."
        )
        return _render_dashboard(
            request,
            db,
            selected_year=academic_year,
            error=error_message,
            focus_section=EXCLUDED_PERIODS_SECTION_ID,
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    period.start_date = start_date
    period.end_date = end_date
    period.label = (label or "").strip() or None
    db.commit()
    return RedirectResponse(
        url=_year_dashboard_url(academic_year.id, status_name="period-updated", section_id=EXCLUDED_PERIODS_SECTION_ID),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/years/{year_id}/periods/{period_id}/delete")
def delete_period(year_id: int, period_id: int, db: Session = Depends(get_db), _: AdminUser = Depends(require_admin)):
    """Delete one previously saved excluded period."""

    period = db.get(ExcludedPeriod, period_id)
    if period and period.academic_year_id == year_id:
        db.delete(period)
        db.commit()
    return RedirectResponse(
        url=_year_dashboard_url(year_id, status_name="period-deleted", section_id=EXCLUDED_PERIODS_SECTION_ID),
        status_code=status.HTTP_303_SEE_OTHER,
    )


def _build_week_groups(db: Session, academic_year: AcademicYear) -> list[dict[str, object]]:
    """Prepare the week grid, grouped by month, for one academic year."""

    week_starts = iter_week_starts(academic_year.default_start_date, academic_year.default_end_date)
    periods = _periods_for_year(db, academic_year.id)
    excluded_dates = expand_excluded_periods([(period.start_date, period.end_date) for period in periods])
    suggestions = suggest_week_numbers(week_starts, excluded_dates)
    saved_numbers = {
        row.week_start_date: row.number
        for row in db.scalars(select(AcademicWeekNumber).where(AcademicWeekNumber.academic_year_id == academic_year.id)).all()
    }

    groups: list[dict[str, object]] = []
    groups_by_month: dict[str, dict[str, object]] = {}
    for monday in week_starts:
        month_label = format_month_label(monday)
        group = groups_by_month.get(month_label)
        if group is None:
            group = {"label": month_label, "weeks": []}
            groups_by_month[month_label] = group
            groups.append(group)
        number = saved_numbers.get(monday, suggestions.get(monday))
        group["weeks"].append(
            {
                "field_name": f"{WEEK_FIELD_PREFIX}{monday.isoformat()}",
                "start": monday,
                "end": monday + timedelta(days=6),
                "number": number,
                "is_vacation_week": is_vacation_week(number, monday, excluded_dates),
            }
        )
    return groups


@router.get("/years/{year_id}/weeks")
def weeks_page(request: Request, year_id: int, db: Session = Depends(get_db), _: AdminUser = Depends(require_admin)):
    """Show the week-numbering grid for one academic year."""

    academic_year = db.get(AcademicYear, year_id)
    if academic_year is None:
        return RedirectResponse(url="/admin", status_code=status.HTTP_303_SEE_OTHER)

    status_message, status_tone = _status_from_request(request)
    return templates.TemplateResponse(
        request,
        "admin/weeks.html",
        {
            "selected_year": academic_year,
            "week_groups": _build_week_groups(db, academic_year),
            "include_week_numbers_in_export": academic_year.include_week_numbers_in_export,
            "status_message": status_message,
            "status_tone": status_tone,
            "error": None,
        },
    )


@router.post("/years/{year_id}/weeks")
async def update_weeks(request: Request, year_id: int, db: Session = Depends(get_db), _: AdminUser = Depends(require_admin)):
    """Bulk-save the week-numbering grid for one academic year."""

    academic_year = db.get(AcademicYear, year_id)
    if academic_year is None:
        return RedirectResponse(url="/admin", status_code=status.HTTP_303_SEE_OTHER)

    form_data = dict(await request.form())
    week_starts = iter_week_starts(academic_year.default_start_date, academic_year.default_end_date)
    existing_rows = {
        row.week_start_date: row
        for row in db.scalars(select(AcademicWeekNumber).where(AcademicWeekNumber.academic_year_id == academic_year.id)).all()
    }

    for monday in week_starts:
        raw_value = (form_data.get(f"{WEEK_FIELD_PREFIX}{monday.isoformat()}") or "").strip()
        existing_row = existing_rows.get(monday)

        if not raw_value:
            if existing_row is not None:
                db.delete(existing_row)
            continue

        try:
            number = int(raw_value)
            if number <= 0:
                raise ValueError
        except ValueError:
            return templates.TemplateResponse(
                request,
                "admin/weeks.html",
                {
                    "selected_year": academic_year,
                    "week_groups": _build_week_groups(db, academic_year),
                    "include_week_numbers_in_export": academic_year.include_week_numbers_in_export,
                    "status_message": None,
                    "status_tone": None,
                    "error": f"El número de la setmana del {format_display_date(monday)} no és vàlid.",
                },
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        if existing_row is not None:
            existing_row.number = number
        else:
            db.add(AcademicWeekNumber(academic_year_id=academic_year.id, week_start_date=monday, number=number))

    db.commit()
    return RedirectResponse(
        url=f"/admin/years/{academic_year.id}/weeks?status=weeks-updated",
        status_code=status.HTTP_303_SEE_OTHER,
    )
