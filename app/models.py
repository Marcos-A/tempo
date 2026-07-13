"""Database models for the small amount of persistent state this MVP needs."""

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AdminUser(Base):
    """Login account for the protected admin area."""

    __tablename__ = "admin_users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AcademicYearSetting(Base):
    """Single-row table holding the default planning window for teachers."""

    __tablename__ = "academic_year_settings"

    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    label: Mapped[str | None] = mapped_column(String(50), nullable=True)
    default_start_date: Mapped[date] = mapped_column(Date)
    default_end_date: Mapped[date] = mapped_column(Date)
    include_week_numbers_in_export: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AcademicYearArchive(Base):
    """Read-only snapshot of a previous academic year's default planning window.

    Written automatically when the admin changes the active dates in
    AcademicYearSetting, so past years stay consultable without the
    singleton settings row needing to track more than "the current one".
    """

    __tablename__ = "academic_year_archive"

    id: Mapped[int] = mapped_column(primary_key=True)
    label: Mapped[str] = mapped_column(String(50))
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    archived_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ExcludedPeriod(Base):
    """Inclusive date range representing days with no classes."""

    __tablename__ = "excluded_periods"

    id: Mapped[int] = mapped_column(primary_key=True)
    start_date: Mapped[date] = mapped_column(Date, index=True)
    end_date: Mapped[date] = mapped_column(Date, index=True)
    label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AcademicWeekNumber(Base):
    """Admin-assigned week number for one Monday-to-Sunday calendar week.

    Keyed by the Monday that starts the week, so a week's end is implicit
    (six days later) and never needs to be kept in sync separately.
    """

    __tablename__ = "academic_week_numbers"

    id: Mapped[int] = mapped_column(primary_key=True)
    week_start_date: Mapped[date] = mapped_column(Date, unique=True, index=True)
    number: Mapped[int] = mapped_column(Integer)
