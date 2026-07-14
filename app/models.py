"""Database models for the small amount of persistent state this MVP needs."""

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AdminUser(Base):
    """Login account for the protected admin area."""

    __tablename__ = "admin_users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AcademicYear(Base):
    """One academic year that can be edited, activated, or removed."""

    __tablename__ = "academic_years"

    id: Mapped[int] = mapped_column(primary_key=True)
    label: Mapped[str] = mapped_column(String(50))
    default_start_date: Mapped[date] = mapped_column(Date)
    default_end_date: Mapped[date] = mapped_column(Date)
    include_week_numbers_in_export: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ExcludedPeriod(Base):
    """Inclusive date range representing days with no classes."""

    __tablename__ = "excluded_periods"

    id: Mapped[int] = mapped_column(primary_key=True)
    academic_year_id: Mapped[int | None] = mapped_column(ForeignKey("academic_years.id"), index=True, nullable=True)
    start_date: Mapped[date] = mapped_column(Date, index=True)
    end_date: Mapped[date] = mapped_column(Date, index=True)
    label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AcademicWeekNumber(Base):
    """Admin-assigned week number for one Monday-to-Sunday calendar week."""

    __tablename__ = "academic_week_numbers"

    id: Mapped[int] = mapped_column(primary_key=True)
    academic_year_id: Mapped[int | None] = mapped_column(ForeignKey("academic_years.id"), index=True, nullable=True)
    week_start_date: Mapped[date] = mapped_column(Date, unique=True, index=True)
    number: Mapped[int] = mapped_column(Integer)
