"""Helpers for working with academic years across admin and teacher flows."""

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AcademicYear


def suggest_year_label(start_date: date, end_date: date) -> str:
    """Derive a compact school-year label from a date range."""

    if start_date.year == end_date.year:
        return str(start_date.year)
    return f"{start_date.year}-{end_date.year % 100:02d}"


def list_academic_years(db: Session) -> list[AcademicYear]:
    """Return academic years with the active one first, then newest to oldest."""

    return db.scalars(
        select(AcademicYear).order_by(AcademicYear.is_active.desc(), AcademicYear.default_start_date.desc(), AcademicYear.id.desc())
    ).all()


def get_active_academic_year(db: Session) -> AcademicYear:
    """Return the active academic year, assuming bootstrap already created one."""

    active_year = db.scalar(
        select(AcademicYear)
        .where(AcademicYear.is_active.is_(True))
        .order_by(AcademicYear.updated_at.desc(), AcademicYear.id.desc())
    )
    if active_year is None:
        raise RuntimeError("No hi ha cap curs acadèmic actiu configurat.")
    return active_year


def activate_academic_year(db: Session, target_year: AcademicYear) -> None:
    """Mark one academic year as active and deactivate the others."""

    for academic_year in db.scalars(select(AcademicYear)).all():
        academic_year.is_active = academic_year.id == target_year.id


def date_ranges_overlap(start_date: date, end_date: date, other_start: date, other_end: date) -> bool:
    """Return whether two inclusive date ranges overlap."""

    return start_date <= other_end and end_date >= other_start


def find_overlapping_year(db: Session, start_date: date, end_date: date, exclude_year_id: int | None = None) -> AcademicYear | None:
    """Find an existing academic year whose range overlaps the proposed one."""

    for academic_year in db.scalars(select(AcademicYear).order_by(AcademicYear.default_start_date, AcademicYear.id)).all():
        if exclude_year_id is not None and academic_year.id == exclude_year_id:
            continue
        if date_ranges_overlap(start_date, end_date, academic_year.default_start_date, academic_year.default_end_date):
            return academic_year
    return None
