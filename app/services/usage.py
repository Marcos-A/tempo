"""Lightweight, anonymous usage counters for the public tools.

Only one number per day and action is stored: no IPs, cookies, or user agents.
"""

import logging
import re
from datetime import date, timedelta

from fastapi import Request
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import UsageDailyCount


logger = logging.getLogger(__name__)

MODULES_VIEW = "modules.view"
MODULES_PLAN = "modules.plan"
MODULES_EXPORT = "modules.export"
INTERNSHIP_VIEW = "internship.view"
INTERNSHIP_EXPORT = "internship.export"
INTERNSHIP_EXPORT_HTML = "internship.export_html"

# (section label, [(event, column label)]) in the order the admin view shows them.
USAGE_SECTIONS = [
    ("Planificació de mòduls", [(MODULES_VIEW, "Visites"), (MODULES_PLAN, "Planificacions"), (MODULES_EXPORT, "Exportacions")]),
    (
        "Calendari de pràctiques",
        [(INTERNSHIP_VIEW, "Visites"), (INTERNSHIP_EXPORT, "Exportacions XLSX"), (INTERNSHIP_EXPORT_HTML, "Exportacions HTML")],
    ),
]

# Uptime monitors, crawlers and scripted clients would otherwise dwarf real visits.
AUTOMATED_USER_AGENT = re.compile(
    r"bot|crawl|spider|slurp|curl|wget|python|httpx|go-http|axios|node-fetch|java/|okhttp|uptime|monitor|headless|preview|facebookexternalhit",
    re.IGNORECASE,
)


def is_automated_request(request: Request) -> bool:
    """Treat requests without a browser-like user agent as non-human traffic."""

    user_agent = request.headers.get("user-agent", "")
    return not user_agent or bool(AUTOMATED_USER_AGENT.search(user_agent))


def record_usage(db: Session, request: Request, event: str, *, today: date | None = None) -> None:
    """Increment today's counter for one event, never failing the caller's request."""

    if is_automated_request(request):
        return

    day = today or date.today()
    increment = (
        update(UsageDailyCount)
        .where(UsageDailyCount.day == day, UsageDailyCount.event == event)
        .values(count=UsageDailyCount.count + 1)
    )
    try:
        if db.execute(increment).rowcount == 0:
            try:
                with db.begin_nested():
                    db.add(UsageDailyCount(day=day, event=event, count=1))
            except IntegrityError:
                # Another worker created today's row first; bump that one instead.
                db.execute(increment)
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        logger.exception("Could not record usage event %s", event)


def usage_summary(db: Session, *, today: date | None = None, weeks: int = 12) -> dict[str, object]:
    """Aggregate the daily counters into rolling totals and a per-week table."""

    today = today or date.today()
    rows = db.scalars(select(UsageDailyCount)).all()
    current_monday = today - timedelta(days=today.weekday())
    week_starts = [current_monday - timedelta(weeks=offset) for offset in range(weeks)]

    totals = {event: {"last_7": 0, "last_30": 0, "all": 0} for _, events in USAGE_SECTIONS for event, _ in events}
    weekly = {monday: {event: 0 for event in totals} for monday in week_starts}
    for row in rows:
        if row.event not in totals:
            continue
        age = (today - row.day).days
        totals[row.event]["all"] += row.count
        if 0 <= age < 30:
            totals[row.event]["last_30"] += row.count
        if 0 <= age < 7:
            totals[row.event]["last_7"] += row.count
        monday = row.day - timedelta(days=row.day.weekday())
        if monday in weekly:
            weekly[monday][row.event] += row.count

    return {
        "sections": USAGE_SECTIONS,
        "totals": totals,
        "weekly": [{"week_start": monday, "counts": weekly[monday]} for monday in week_starts],
        "tracking_since": min((row.day for row in rows), default=None),
    }
