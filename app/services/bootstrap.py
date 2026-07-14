"""Startup helpers that seed the minimum data required by the app."""

from datetime import date

from sqlalchemy import inspect, select, text
from sqlalchemy.orm import Session

from app.auth import hash_password, verify_password
from app.config import get_settings
from app.models import AcademicWeekNumber, AcademicYear, AdminUser, ExcludedPeriod
from app.services.academic_years import suggest_year_label


def _coerce_sql_date(value) -> date:
    """Convert raw SQLite values into ``date`` instances."""

    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def _ensure_column(db: Session, inspector, table_name: str, column_name: str, ddl: str) -> None:
    """Add one column to a legacy SQLite table when it is still missing."""

    table_names = inspector.get_table_names()
    if table_name not in table_names:
        return
    columns = {column["name"] for column in inspector.get_columns(table_name)}
    if column_name in columns:
        return
    db.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {ddl}"))
    db.commit()


def _seed_academic_years_from_legacy_tables(db: Session, inspector) -> None:
    """Create the new academic-year rows from the legacy singleton/archive tables."""

    legacy_current = None
    if "academic_year_settings" in inspector.get_table_names():
        legacy_current = db.execute(
            text(
                "SELECT label, default_start_date, default_end_date, include_week_numbers_in_export "
                "FROM academic_year_settings WHERE id = 1"
            )
        ).mappings().first()

    if legacy_current is not None:
        current_start = _coerce_sql_date(legacy_current["default_start_date"])
        current_end = _coerce_sql_date(legacy_current["default_end_date"])
        db.add(
            AcademicYear(
                label=(legacy_current["label"] or "").strip() or suggest_year_label(current_start, current_end),
                default_start_date=current_start,
                default_end_date=current_end,
                include_week_numbers_in_export=bool(legacy_current["include_week_numbers_in_export"]),
                is_active=True,
            )
        )
    else:
        db.add(
            AcademicYear(
                label=suggest_year_label(date(date.today().year, 9, 1), date(date.today().year + 1, 6, 30)),
                default_start_date=date(date.today().year, 9, 1),
                default_end_date=date(date.today().year + 1, 6, 30),
                include_week_numbers_in_export=False,
                is_active=True,
            )
        )

    if "academic_year_archive" in inspector.get_table_names():
        for row in db.execute(
            text("SELECT label, start_date, end_date FROM academic_year_archive ORDER BY start_date DESC, id DESC")
        ).mappings():
            archive_start = _coerce_sql_date(row["start_date"])
            archive_end = _coerce_sql_date(row["end_date"])
            db.add(
                AcademicYear(
                    label=(row["label"] or "").strip() or suggest_year_label(archive_start, archive_end),
                    default_start_date=archive_start,
                    default_end_date=archive_end,
                    include_week_numbers_in_export=False,
                    is_active=False,
                )
            )
    db.flush()


def _matching_year_ids_for_period(period: ExcludedPeriod, academic_years: list[AcademicYear]) -> list[int]:
    """Return academic years whose ranges overlap an excluded period."""

    return [
        academic_year.id
        for academic_year in academic_years
        if academic_year.default_start_date <= period.end_date and academic_year.default_end_date >= period.start_date
    ]


def _matching_year_ids_for_week(row: AcademicWeekNumber, academic_years: list[AcademicYear]) -> list[int]:
    """Return academic years whose ranges contain a saved week start."""

    return [
        academic_year.id
        for academic_year in academic_years
        if academic_year.default_start_date <= row.week_start_date <= academic_year.default_end_date
    ]


def _backfill_year_ownership(db: Session) -> None:
    """Attach legacy exclusions and week numbers to the most plausible academic year."""

    academic_years = db.scalars(select(AcademicYear).order_by(AcademicYear.default_start_date, AcademicYear.id)).all()
    active_year = next((academic_year for academic_year in academic_years if academic_year.is_active), None)
    if active_year is None and academic_years:
        active_year = academic_years[-1]
        active_year.is_active = True

    for period in db.scalars(select(ExcludedPeriod).where(ExcludedPeriod.academic_year_id.is_(None))).all():
        matching_year_ids = _matching_year_ids_for_period(period, academic_years)
        if len(matching_year_ids) == 1:
            period.academic_year_id = matching_year_ids[0]
        elif active_year is not None and active_year.id in matching_year_ids:
            period.academic_year_id = active_year.id
        elif matching_year_ids:
            period.academic_year_id = matching_year_ids[0]
        elif active_year is not None:
            period.academic_year_id = active_year.id

    for row in db.scalars(select(AcademicWeekNumber).where(AcademicWeekNumber.academic_year_id.is_(None))).all():
        matching_year_ids = _matching_year_ids_for_week(row, academic_years)
        if len(matching_year_ids) == 1:
            row.academic_year_id = matching_year_ids[0]
        elif active_year is not None and active_year.id in matching_year_ids:
            row.academic_year_id = active_year.id
        elif matching_year_ids:
            row.academic_year_id = matching_year_ids[0]
        elif active_year is not None:
            row.academic_year_id = active_year.id


def _ensure_single_active_year(db: Session) -> None:
    """Guarantee that exactly one academic year remains active."""

    academic_years = db.scalars(select(AcademicYear).order_by(AcademicYear.default_start_date.desc(), AcademicYear.id.desc())).all()
    if not academic_years:
        return

    active_years = [academic_year for academic_year in academic_years if academic_year.is_active]
    if not active_years:
        academic_years[0].is_active = True
        return

    keeper_id = active_years[0].id
    for academic_year in academic_years:
        academic_year.is_active = academic_year.id == keeper_id


def bootstrap_database(db: Session) -> None:
    """Create the initial admin user and default academic year if missing."""

    settings = get_settings()
    inspector = inspect(db.bind)

    _ensure_column(db, inspector, "excluded_periods", "label", "label VARCHAR(255)")
    inspector = inspect(db.bind)
    _ensure_column(
        db,
        inspector,
        "academic_year_settings",
        "include_week_numbers_in_export",
        "include_week_numbers_in_export BOOLEAN NOT NULL DEFAULT 0",
    )
    inspector = inspect(db.bind)
    _ensure_column(db, inspector, "academic_year_settings", "label", "label VARCHAR(50)")
    inspector = inspect(db.bind)
    _ensure_column(db, inspector, "excluded_periods", "academic_year_id", "academic_year_id INTEGER")
    inspector = inspect(db.bind)
    _ensure_column(db, inspector, "academic_week_numbers", "academic_year_id", "academic_year_id INTEGER")

    admin = db.scalar(select(AdminUser).where(AdminUser.username == settings.admin_username))
    if admin is None:
        db.add(AdminUser(username=settings.admin_username, password_hash=hash_password(settings.admin_password)))
    elif not verify_password(settings.admin_password, admin.password_hash):
        # Keep the configured admin credentials usable across container rebuilds
        # even when an older password hash already exists in the persisted DB.
        admin.password_hash = hash_password(settings.admin_password)

    if db.scalar(select(AcademicYear.id).limit(1)) is None:
        inspector = inspect(db.bind)
        _seed_academic_years_from_legacy_tables(db, inspector)

    _ensure_single_active_year(db)
    _backfill_year_ownership(db)
    db.commit()
