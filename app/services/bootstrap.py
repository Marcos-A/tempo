"""Startup helpers that seed the minimum data required by the app."""

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import hash_password
from app.config import get_settings
from app.models import AcademicYearSetting, AdminUser


def bootstrap_database(db: Session) -> None:
    """Create the initial admin user and default academic year if missing."""

    settings = get_settings()

    admin = db.scalar(select(AdminUser).where(AdminUser.username == settings.admin_username))
    if admin is None:
        db.add(AdminUser(username=settings.admin_username, password_hash=hash_password(settings.admin_password)))

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
