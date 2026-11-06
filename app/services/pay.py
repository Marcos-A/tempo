"""The intensive modality's pay estimate: its settings, inputs and calculation.

The admin sets the monthly minimum wage (SMI, paid 14 times a year) once; the
planner offers it as the default, and each plan can change it. Amounts are
kept in whole cents.

The student is paid by the hour for the hours actually planned. The hourly
reference is the SMI's yearly amount spread over 12 months of 20 days of 8 h:
1.221,00 € × 14 = 17.094 € ÷ 12 = 1.424,50 € ÷ 20 = 71,225 € ÷ 8 = 8,90 €/h.
Grau mitjà is paid 50 % of it throughout; grau superior 60 % for the first
half of the agreement's hours and 70 % for the second half.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from fractions import Fraction
from typing import Protocol

from sqlalchemy.orm import Session

from app.models import AppSetting
from app.services.hours import MINUTES_PER_HOUR, format_minutes_label

SMI_SETTING_KEY = "internship_smi"
MAX_SMI_CENTS = 100_000 * 100
GRADE_LABELS = {"mitja": "Grau mitjà", "superior": "Grau superior"}
# A grade is always selected; this one applies until the user or the training cycle says otherwise.
DEFAULT_GRADE = "mitja"

SMI_PAYMENTS_PER_YEAR = 14
MONTHS_PER_YEAR = 12
WORKING_DAYS_PER_MONTH = 20
HOURS_PER_WORKING_DAY = 8
# Percentage of the hourly reference for the first and second half of the hours.
GRADE_PERCENTS = {"mitja": (50, 50), "superior": (60, 70)}


class PlannedDay(Protocol):
    date: date
    minutes: int


@dataclass(frozen=True)
class PayEstimate:
    """A plan's estimated pay, in cents; months without hours are left out."""

    hourly_cents: Fraction
    percents: tuple[int, int]
    month_cents: dict[str, int]
    month_labels: dict[str, str]
    total_cents: int
    note: str
    # Set when the hours reach a later calendar year, whose SMI may be different.
    smi_notice: str = ""

    def summary(self) -> dict[str, object]:
        """What the planner and the exports show."""

        return {
            "total": f"{format_euros(self.total_cents)} €",
            "note": self.note,
            "smi_notice": self.smi_notice,
            "months": self.month_labels,
        }


def month_key(day: date) -> str:
    return f"{day.year}-{day.month:02d}"


def _whole_cents(amount: Fraction) -> int:
    """Round half up, the way a spreadsheet's ROUND does for positive amounts."""

    return int(amount + Fraction(1, 2))


def _hourly_label(hourly_cents: Fraction, percent: int) -> str:
    return f"{percent} % ({format_euros(_whole_cents(hourly_cents * percent / 100))} €/h)"


def _estimate_note(smi_cents: int, hourly_cents: Fraction, grade: str, target_minutes: int) -> str:
    first, second = GRADE_PERCENTS[grade]
    formula = (
        f"{format_euros(smi_cents)} € × {SMI_PAYMENTS_PER_YEAR} pagues ÷ {MONTHS_PER_YEAR} mesos ÷ "
        f"{WORKING_DAYS_PER_MONTH} dies ÷ {HOURS_PER_WORKING_DAY} h = {format_euros(_whole_cents(hourly_cents))} €/h"
    )
    if first == second:
        rates = f"{GRADE_LABELS[grade]}: {_hourly_label(hourly_cents, first)} per a totes les hores"
    else:
        half = format_minutes_label(target_minutes // 2)
        rates = (
            f"{GRADE_LABELS[grade]}: {_hourly_label(hourly_cents, first)} fins a les {half} "
            f"i {_hourly_label(hourly_cents, second)} a partir d'aquí"
        )
    return f"Estimació orientativa, no és una nòmina. {formula}. {rates}."


def estimate_pay(days: Iterable[PlannedDay], target_minutes: int, grade: str, smi_cents: int) -> PayEstimate:
    """Estimate the pay of each month from the plan's minutes.

    Half of the hours means half of the agreement's total, so a month can hold
    both rates and a plan that stops short of its total keeps the same rates.
    The total adds up the rounded months, so it matches what is shown for each.
    Every month uses the same SMI; hours in a later calendar year add a notice,
    because the SMI usually changes with the new year.
    """

    first, second = GRADE_PERCENTS[grade]
    hourly_cents = Fraction(
        smi_cents * SMI_PAYMENTS_PER_YEAR, MONTHS_PER_YEAR * WORKING_DAYS_PER_MONTH * HOURS_PER_WORKING_DAY
    )
    half = Fraction(target_minutes, 2)

    # Each month's minutes at the first and at the second rate.
    months: dict[str, list[Fraction]] = {}
    cumulative = 0
    worked_years: set[int] = set()
    for day in days:
        if not day.minutes:
            continue
        worked_years.add(day.date.year)
        at_first = min(cumulative + day.minutes, half) - min(cumulative, half)
        month = months.setdefault(month_key(day.date), [Fraction(0), Fraction(0)])
        month[0] += at_first
        month[1] += day.minutes - at_first
        cumulative += day.minutes

    month_cents: dict[str, int] = {}
    month_labels: dict[str, str] = {}
    for key, (at_first, at_second) in months.items():
        weighted_minutes = at_first * first + at_second * second
        month_cents[key] = _whole_cents(hourly_cents * weighted_minutes / (MINUTES_PER_HOUR * 100))
        if first == second or not at_second:
            percents = f"{first} %"
        elif not at_first:
            percents = f"{second} %"
        else:
            percents = f"{first} % i {second} %"
        month_labels[key] = f"≈ {format_euros(month_cents[key])} € · {percents}"

    return PayEstimate(
        hourly_cents=hourly_cents,
        percents=(first, second),
        month_cents=month_cents,
        month_labels=month_labels,
        total_cents=sum(month_cents.values()),
        note=_estimate_note(smi_cents, hourly_cents, grade, target_minutes),
        smi_notice=(
            f"L'SMI sol canviar amb l'any nou i aquest calendari arriba al {max(worked_years)}: "
            "l'estimació aplica el mateix SMI a tots els mesos, així que cal revisar-lo quan es publiqui el nou import."
            if len(worked_years) > 1
            else ""
        ),
    )


def parse_euros(raw: str) -> int:
    """Return a euro amount such as 1.221,00, 1221,5 or 1221 in cents.

    A comma is the decimal separator; dots group thousands. A dot followed
    by one or two digits at the end is also read as decimals (1184.50).
    """

    text = raw.replace("€", "").replace(" ", "").strip()
    if "," in text:
        text = text.replace(".", "").replace(",", ".")
    elif re.fullmatch(r"\d{1,3}(\.\d{3})+", text):
        text = text.replace(".", "")
    if not re.fullmatch(r"\d+(\.\d{1,2})?", text):
        raise ValueError("Indica l'SMI mensual en euros, p. ex. 1.221,00.")
    whole, _, decimals = text.partition(".")
    cents = int(whole) * 100 + int(decimals.ljust(2, "0") or 0)
    if not 0 < cents <= MAX_SMI_CENTS:
        raise ValueError("L'SMI ha de ser superior a zero i inferior a 100.000 €.")
    return cents


def format_euros(cents: int) -> str:
    """Return cents as a Catalan amount without the symbol, e.g. 1.221,00."""

    whole, rest = divmod(cents, 100)
    return f"{whole:,}".replace(",", ".") + f",{rest:02d}"


def get_smi_cents(db: Session) -> int | None:
    setting = db.get(AppSetting, SMI_SETTING_KEY)
    return int(setting.value) if setting is not None and setting.value else None


def set_smi_cents(db: Session, cents: int | None) -> None:
    """Store the admin's SMI, or clear it so each plan has to give its own."""

    setting = db.get(AppSetting, SMI_SETTING_KEY) or AppSetting(key=SMI_SETTING_KEY)
    setting.value = str(cents) if cents is not None else None
    db.add(setting)
    db.commit()
