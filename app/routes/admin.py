"""Routes for the protected admin area."""

from typing import Annotated

from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import verify_password
from app.database import get_db
from app.date_utils import format_display_date, parse_date_input
from app.dependencies import require_admin
from app.models import AcademicYearSetting, AdminUser, ExcludedPeriod


router = APIRouter(prefix="/admin", tags=["admin"])
templates = Jinja2Templates(directory="app/templates")
templates.env.filters["date_display"] = format_display_date
EXCLUDED_PERIODS_SECTION_ID = "excluded-periods"


def _render_dashboard(
    request: Request,
    settings: AcademicYearSetting,
    periods: list[ExcludedPeriod],
    error: str | None = None,
    focus_section: str | None = None,
    status_code: int = status.HTTP_200_OK,
):
    """Render the admin dashboard with the provided context."""

    return templates.TemplateResponse(
        request,
        "admin/dashboard.html",
        {"settings": settings, "periods": periods, "error": error, "focus_section": focus_section},
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
    """Show the settings page for dates and excluded periods."""

    settings = db.get(AcademicYearSetting, 1)
    periods = db.scalars(select(ExcludedPeriod).order_by(ExcludedPeriod.start_date, ExcludedPeriod.end_date)).all()
    error = None
    focus_section = None
    if request.query_params.get("error") == "invalid-period":
        error = "La data de fi no pot ser anterior a la data d'inici."
        focus_section = EXCLUDED_PERIODS_SECTION_ID
    return _render_dashboard(request, settings, periods, error=error, focus_section=focus_section)


@router.post("/settings")
def update_settings(
    request: Request,
    default_start_date_raw: str = Form(..., alias="default_start_date"),
    default_end_date_raw: str = Form(..., alias="default_end_date"),
    db: Session = Depends(get_db),
    _: AdminUser = Depends(require_admin),
):
    """Update the default planning window used by the teacher form."""

    settings = db.get(AcademicYearSetting, 1)
    periods = db.scalars(select(ExcludedPeriod).order_by(ExcludedPeriod.start_date, ExcludedPeriod.end_date)).all()

    try:
        default_start_date = parse_date_input(default_start_date_raw)
        default_end_date = parse_date_input(default_end_date_raw)
    except ValueError as exc:
        return _render_dashboard(
            request,
            settings,
            periods,
            error=str(exc),
            focus_section=EXCLUDED_PERIODS_SECTION_ID,
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    if default_end_date < default_start_date:
        return _render_dashboard(
            request,
            settings,
            periods,
            error="La data de fi no pot ser anterior a la data d'inici.",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    settings.default_start_date = default_start_date
    settings.default_end_date = default_end_date
    db.commit()
    return RedirectResponse(url="/admin", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/periods")
def add_period(
    request: Request,
    start_date_raw: str = Form(..., alias="start_date"),
    end_date_raw: Annotated[str | None, Form(alias="end_date")] = None,
    label: Annotated[str | None, Form()] = None,
    db: Session = Depends(get_db),
    _: AdminUser = Depends(require_admin),
):
    """Store a no-class day or an inclusive no-class range.

    The form allows a blank end date for convenience. In that case we interpret
    the submission as a single excluded day.
    """

    settings = db.get(AcademicYearSetting, 1)
    periods = db.scalars(select(ExcludedPeriod).order_by(ExcludedPeriod.start_date, ExcludedPeriod.end_date)).all()

    try:
        start_date = parse_date_input(start_date_raw)
        end_date = start_date if not end_date_raw else parse_date_input(end_date_raw)
    except ValueError as exc:
        return _render_dashboard(
            request,
            settings,
            periods,
            error=str(exc),
            focus_section=EXCLUDED_PERIODS_SECTION_ID,
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    if end_date < start_date:
        return RedirectResponse(url="/admin?error=invalid-period", status_code=status.HTTP_303_SEE_OTHER)

    existing_period = db.scalar(
        select(ExcludedPeriod).where(
            ExcludedPeriod.start_date == start_date,
            ExcludedPeriod.end_date == end_date,
        )
    )
    if existing_period is not None:
        error_message = (
            "Aquesta data sense classe ja existeix."
            if start_date == end_date
            else "Aquest període sense classe ja existeix."
        )
        return _render_dashboard(
            request,
            settings,
            periods,
            error=error_message,
            focus_section=EXCLUDED_PERIODS_SECTION_ID,
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    db.add(ExcludedPeriod(start_date=start_date, end_date=end_date, label=(label or "").strip() or None))
    db.commit()
    return RedirectResponse(url=f"/admin#{EXCLUDED_PERIODS_SECTION_ID}", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/periods/{period_id}")
def update_period(
    request: Request,
    period_id: int,
    start_date_raw: str = Form(..., alias="start_date"),
    end_date_raw: Annotated[str | None, Form(alias="end_date")] = None,
    label: Annotated[str | None, Form()] = None,
    db: Session = Depends(get_db),
    _: AdminUser = Depends(require_admin),
):
    """Edit one previously saved excluded period."""

    settings = db.get(AcademicYearSetting, 1)
    periods = db.scalars(select(ExcludedPeriod).order_by(ExcludedPeriod.start_date, ExcludedPeriod.end_date)).all()
    period = db.get(ExcludedPeriod, period_id)

    if period is None:
        return RedirectResponse(url=f"/admin#{EXCLUDED_PERIODS_SECTION_ID}", status_code=status.HTTP_303_SEE_OTHER)

    try:
        start_date = parse_date_input(start_date_raw)
        end_date = start_date if not end_date_raw else parse_date_input(end_date_raw)
    except ValueError as exc:
        return _render_dashboard(
            request,
            settings,
            periods,
            error=str(exc),
            focus_section=EXCLUDED_PERIODS_SECTION_ID,
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    if end_date < start_date:
        return RedirectResponse(url="/admin?error=invalid-period", status_code=status.HTTP_303_SEE_OTHER)

    existing_period = db.scalar(
        select(ExcludedPeriod).where(
            ExcludedPeriod.start_date == start_date,
            ExcludedPeriod.end_date == end_date,
            ExcludedPeriod.id != period_id,
        )
    )
    if existing_period is not None:
        error_message = (
            "Aquesta data sense classe ja existeix."
            if start_date == end_date
            else "Aquest període sense classe ja existeix."
        )
        return _render_dashboard(
            request,
            settings,
            periods,
            error=error_message,
            focus_section=EXCLUDED_PERIODS_SECTION_ID,
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    period.start_date = start_date
    period.end_date = end_date
    period.label = (label or "").strip() or None
    db.commit()
    return RedirectResponse(url=f"/admin#{EXCLUDED_PERIODS_SECTION_ID}", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/periods/{period_id}/delete")
def delete_period(period_id: int, db: Session = Depends(get_db), _: AdminUser = Depends(require_admin)):
    """Delete one previously saved excluded period."""

    period = db.get(ExcludedPeriod, period_id)
    if period:
        db.delete(period)
        db.commit()
    return RedirectResponse(url="/admin", status_code=status.HTTP_303_SEE_OTHER)
