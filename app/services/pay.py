"""Settings and inputs for the intensive modality's pay estimate.

The admin sets the minimum wage (SMI) once; the planner offers it as the
default, and each plan can change it. Amounts are kept in whole cents.
"""

from __future__ import annotations

import re

from sqlalchemy.orm import Session

from app.models import AppSetting

SMI_SETTING_KEY = "internship_smi"
MAX_SMI_CENTS = 100_000 * 100
GRADE_LABELS = {"mitja": "Grau mitjà", "superior": "Grau superior"}


def parse_euros(raw: str) -> int:
    """Return a euro amount such as 1.184,00, 1184,5 or 1184 in cents.

    A comma is the decimal separator; dots group thousands. A dot followed
    by one or two digits at the end is also read as decimals (1184.50).
    """

    text = raw.replace("€", "").replace(" ", "").strip()
    if "," in text:
        text = text.replace(".", "").replace(",", ".")
    elif re.fullmatch(r"\d{1,3}(\.\d{3})+", text):
        text = text.replace(".", "")
    if not re.fullmatch(r"\d+(\.\d{1,2})?", text):
        raise ValueError("Indica l'SMI en euros, p. ex. 1.184,00.")
    whole, _, decimals = text.partition(".")
    cents = int(whole) * 100 + int(decimals.ljust(2, "0") or 0)
    if not 0 < cents <= MAX_SMI_CENTS:
        raise ValueError("L'SMI ha de ser superior a zero i inferior a 100.000 €.")
    return cents


def format_euros(cents: int) -> str:
    """Return cents as a Catalan amount without the symbol, e.g. 1.184,00."""

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
