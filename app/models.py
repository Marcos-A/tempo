"""Database models for the small amount of persistent state this MVP needs."""

from datetime import date, datetime

from sqlalchemy import Date, DateTime, String
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
    default_start_date: Mapped[date] = mapped_column(Date)
    default_end_date: Mapped[date] = mapped_column(Date)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ExcludedPeriod(Base):
    """Inclusive date range representing days with no classes."""

    __tablename__ = "excluded_periods"

    id: Mapped[int] = mapped_column(primary_key=True)
    start_date: Mapped[date] = mapped_column(Date, index=True)
    end_date: Mapped[date] = mapped_column(Date, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
