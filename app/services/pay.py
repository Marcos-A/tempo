"""The intensive modality's pay estimate: its settings, inputs and calculation.

The admin sets the minimum wage (SMI) once, and chooses whether it is given
as the monthly amount (one of its 14 payments) or as the annual one. That
choice applies everywhere: the planner, the exports and every plan show and
take the SMI in that form only. The planner offers the admin's amount as the
default, and each plan can change it. Amounts are kept in whole cents.

The student is paid by the hour for the hours actually planned. The hourly
reference is the SMI's yearly amount spread over 12 months of 20 days of 8 h:
1.221,00 € × 14 = 17.094 € ÷ 12 = 1.424,50 € ÷ 20 = 71,225 € ÷ 8 = 8,90 €/h.
An annual SMI is that yearly amount already (17.094 €). A monthly SMI is one
of the 14 payments, never the amount with the extra payments prorated over
12 months (1.424,50 €), which would overstate the estimate by 14/12.
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
SMI_PERIOD_SETTING_KEY = "internship_smi_period"
SMI_MONTHLY = "mensual"
SMI_ANNUAL = "anual"
SMI_PERIOD_LABELS = {SMI_MONTHLY: "SMI mensual", SMI_ANNUAL: "SMI anual"}
# Plans saved before the admin could choose had a monthly SMI.
DEFAULT_SMI_PERIOD = SMI_MONTHLY
SMI_EXAMPLES = {SMI_MONTHLY: "1.221,00", SMI_ANNUAL: "17.094,00"}
# The last amount the admin saved in each form, so switching back brings it
# back exactly instead of a rounded conversion.
SMI_AMOUNT_SETTING_KEYS = {period: f"internship_smi_{period}" for period in SMI_PERIOD_LABELS}
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


def annual_smi_cents(smi_cents: int, period: str) -> int:
    return smi_cents * SMI_PAYMENTS_PER_YEAR if period == SMI_MONTHLY else smi_cents


def convert_smi_cents(smi_cents: int, from_period: str, to_period: str) -> int:
    """Express an SMI given monthly or annually in the other form (÷ or × 14 payments)."""

    if from_period == to_period:
        return smi_cents
    if to_period == SMI_ANNUAL:
        return smi_cents * SMI_PAYMENTS_PER_YEAR
    return _whole_cents(Fraction(smi_cents, SMI_PAYMENTS_PER_YEAR))


def _estimate_note(smi_cents: int, period: str, hourly_cents: Fraction, grade: str, target_minutes: int) -> str:
    first, second = GRADE_PERCENTS[grade]
    payments = f" × {SMI_PAYMENTS_PER_YEAR} pagues" if period == SMI_MONTHLY else ""
    formula = (
        f"{format_euros(smi_cents)} €{payments} ÷ {MONTHS_PER_YEAR} mesos ÷ "
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


def estimate_pay(
    days: Iterable[PlannedDay], target_minutes: int, grade: str, smi_cents: int, period: str = SMI_MONTHLY
) -> PayEstimate:
    """Estimate the pay of each month from the plan's minutes.

    Half of the hours means half of the agreement's total, so a month can hold
    both rates and a plan that stops short of its total keeps the same rates.
    The total adds up the rounded months, so it matches what is shown for each.
    Every month uses the same SMI; hours in a later calendar year add a notice,
    because the SMI usually changes with the new year. `period` says whether
    `smi_cents` is the monthly or the annual SMI.
    """

    first, second = GRADE_PERCENTS[grade]
    hourly_cents = Fraction(
        annual_smi_cents(smi_cents, period), MONTHS_PER_YEAR * WORKING_DAYS_PER_MONTH * HOURS_PER_WORKING_DAY
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
        note=_estimate_note(smi_cents, period, hourly_cents, grade, target_minutes),
        smi_notice=(
            f"L'SMI sol canviar amb l'any nou i aquest calendari arriba al {max(worked_years)}: "
            "l'estimació aplica el mateix SMI a tots els mesos, així que cal revisar-lo quan es publiqui el nou import."
            if len(worked_years) > 1
            else ""
        ),
    )


def parse_euros(raw: str, period: str = SMI_MONTHLY) -> int:
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
        raise ValueError(f"Indica l'{SMI_PERIOD_LABELS[period]} en euros, p. ex. {SMI_EXAMPLES[period]}.")
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


def get_smi_period(db: Session) -> str:
    setting = db.get(AppSetting, SMI_PERIOD_SETTING_KEY)
    return setting.value if setting is not None and setting.value in SMI_PERIOD_LABELS else DEFAULT_SMI_PERIOD


def smi_amounts_match(monthly_cents: int, annual_cents: int) -> bool:
    """Whether a monthly and an annual amount are the same SMI (÷ 14, rounded to the cent)."""

    return convert_smi_cents(annual_cents, SMI_ANNUAL, SMI_MONTHLY) == monthly_cents


def get_smi_amounts(db: Session) -> dict[str, int]:
    """The last amount saved in each form; the current one always counts."""

    amounts = {}
    for period, key in SMI_AMOUNT_SETTING_KEYS.items():
        setting = db.get(AppSetting, key)
        if setting is not None and setting.value:
            amounts[period] = int(setting.value)
    current = get_smi_cents(db)
    if current is not None:
        amounts[get_smi_period(db)] = current
    return amounts


def set_smi_cents(db: Session, cents: int | None, period: str | None = None) -> None:
    """Store the admin's SMI, or clear it so each plan has to give its own.

    `period` (monthly or annual) is stored too when given; it applies even
    when the amount is cleared. An amount is also remembered for its form.
    """

    if period is not None and period not in SMI_PERIOD_LABELS:
        raise ValueError("Tipus d'SMI no vàlid.")
    period = period or get_smi_period(db)
    setting = db.get(AppSetting, SMI_SETTING_KEY) or AppSetting(key=SMI_SETTING_KEY)
    setting.value = str(cents) if cents is not None else None
    db.add(setting)
    period_setting = db.get(AppSetting, SMI_PERIOD_SETTING_KEY) or AppSetting(key=SMI_PERIOD_SETTING_KEY)
    period_setting.value = period
    db.add(period_setting)
    if cents is not None:
        key = SMI_AMOUNT_SETTING_KEYS[period]
        remembered = db.get(AppSetting, key) or AppSetting(key=key)
        remembered.value = str(cents)
        db.add(remembered)
    db.commit()
