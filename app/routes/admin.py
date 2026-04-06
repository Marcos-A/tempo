"""Routes for the protected admin area."""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import verify_password
from app.database import get_db
from app.dependencies import require_admin
from app.models import AcademicYearSetting, AdminUser, ExcludedPeriod


router = APIRouter(prefix="/admin", tags=["admin"])
templates = Jinja2Templates(directory="app/templates")


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
    if request.query_params.get("error") == "invalid-period":
        error = "La data de fi no pot ser anterior a la data d'inici."
    return templates.TemplateResponse(
        request,
        "admin/dashboard.html",
        {"settings": settings, "periods": periods, "error": error},
    )


@router.post("/settings")
def update_settings(
    request: Request,
    default_start_date: date = Form(...),
    default_end_date: date = Form(...),
    db: Session = Depends(get_db),
    _: AdminUser = Depends(require_admin),
):
    """Update the default planning window used by the teacher form."""

    if default_end_date < default_start_date:
        settings = db.get(AcademicYearSetting, 1)
        periods = db.scalars(select(ExcludedPeriod).order_by(ExcludedPeriod.start_date, ExcludedPeriod.end_date)).all()
        return templates.TemplateResponse(
            request,
            "admin/dashboard.html",
            {"settings": settings, "periods": periods, "error": "La data de fi no pot ser anterior a la data d'inici."},
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    settings = db.get(AcademicYearSetting, 1)
    settings.default_start_date = default_start_date
    settings.default_end_date = default_end_date
    db.commit()
    return RedirectResponse(url="/admin", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/periods")
def add_period(
    start_date: date = Form(...),
    end_date_raw: Annotated[str | None, Form()] = None,
    db: Session = Depends(get_db),
    _: AdminUser = Depends(require_admin),
):
    """Store a no-class day or an inclusive no-class range.

    The form allows a blank end date for convenience. In that case we interpret
    the submission as a single excluded day.
    """

    end_date = start_date if not end_date_raw else date.fromisoformat(end_date_raw)
    if end_date < start_date:
        return RedirectResponse(url="/admin?error=invalid-period", status_code=status.HTTP_303_SEE_OTHER)
    db.add(ExcludedPeriod(start_date=start_date, end_date=end_date))
    db.commit()
    return RedirectResponse(url="/admin", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/periods/{period_id}/delete")
def delete_period(period_id: int, db: Session = Depends(get_db), _: AdminUser = Depends(require_admin)):
    """Delete one previously saved excluded period."""

    period = db.get(ExcludedPeriod, period_id)
    if period:
        db.delete(period)
        db.commit()
    return RedirectResponse(url="/admin", status_code=status.HTTP_303_SEE_OTHER)
