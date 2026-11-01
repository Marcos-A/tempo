"""Holidays that fall on the same day every year, shared by every academic year."""

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import RecurringHoliday
from app.services.calendar import recurring_dates

# School years start in September, so lists begin there instead of January.
FIRST_SCHOOL_MONTH = 9


def list_recurring_holidays(db: Session) -> list[RecurringHoliday]:
    """Return every recurring holiday in school-year order (September to August)."""

    holidays = db.scalars(select(RecurringHoliday)).all()
    return sorted(holidays, key=lambda holiday: ((holiday.month - FIRST_SCHOOL_MONTH) % 12, holiday.day))


def holiday_tuples(holidays: list[RecurringHoliday]) -> list[tuple[int, int, str]]:
    return [(holiday.month, holiday.day, (holiday.label or "").strip()) for holiday in holidays]


def recurring_holiday_dates(db: Session, start_date: date, end_date: date) -> dict[date, str]:
    """Every occurrence of the recurring holidays in an inclusive range, with its label."""

    return recurring_dates(holiday_tuples(list_recurring_holidays(db)), start_date, end_date)
