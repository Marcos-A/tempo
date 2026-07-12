"""Startup helpers that seed the minimum data required by the app."""

from datetime import date

from sqlalchemy import inspect, select, text
from sqlalchemy.orm import Session

from app.auth import hash_password, verify_password
from app.config import get_settings
from app.models import AcademicYearSetting, AdminUser


def bootstrap_database(db: Session) -> None:
    """Create the initial admin user and default academic year if missing."""

    settings = get_settings()
    inspector = inspect(db.bind)

    if "excluded_periods" in inspector.get_table_names():
        excluded_period_columns = {column["name"] for column in inspector.get_columns("excluded_periods")}
        if "label" not in excluded_period_columns:
            db.execute(text("ALTER TABLE excluded_periods ADD COLUMN label VARCHAR(255)"))
            db.commit()

    if "academic_year_settings" in inspector.get_table_names():
        academic_year_columns = {column["name"] for column in inspector.get_columns("academic_year_settings")}
        if "include_week_numbers_in_export" not in academic_year_columns:
            db.execute(
                text(
                    "ALTER TABLE academic_year_settings "
                    "ADD COLUMN include_week_numbers_in_export BOOLEAN NOT NULL DEFAULT 0"
                )
            )
            db.commit()

    admin = db.scalar(select(AdminUser).where(AdminUser.username == settings.admin_username))
    if admin is None:
        db.add(AdminUser(username=settings.admin_username, password_hash=hash_password(settings.admin_password)))
    elif not verify_password(settings.admin_password, admin.password_hash):
        # Keep the configured admin credentials usable across container rebuilds
        # even when an older password hash already exists in the persisted DB.
        admin.password_hash = hash_password(settings.admin_password)

    default_settings = db.get(AcademicYearSetting, 1)
    if default_settings is None:
        # This is a pragmatic school-year default. Admin can change it later.
        db.add(
            AcademicYearSetting(
                id=1,
                default_start_date=date(date.today().year, 9, 1),
                default_end_date=date(date.today().year + 1, 6, 30),
            )
        )

    db.commit()
