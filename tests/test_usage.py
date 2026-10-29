"""Tests for the anonymous usage counters and their admin view."""

from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.requests import Request

from app.database import Base, get_db
from app.dependencies import require_admin
from app.main import app
from app.models import AcademicYear, UsageDailyCount
from app.services.usage import (
    INTERNSHIP_EXPORT,
    INTERNSHIP_EXPORT_PNG,
    INTERNSHIP_VIEW,
    MODULES_PLAN,
    MODULES_VIEW,
    record_usage,
    usage_summary,
)

BROWSER_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Firefox/131.0"


def _request(user_agent: str) -> Request:
    """Build a minimal request carrying only a user agent."""

    return Request({"type": "http", "method": "GET", "path": "/", "headers": [(b"user-agent", user_agent.encode())], "query_string": b""})


@pytest.fixture()
def session_factory():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(bind=engine)
    with TestingSession() as db:
        db.add(AcademicYear(label="2026-27", default_start_date=date(2026, 9, 7), default_end_date=date(2027, 6, 18), is_active=True))
        db.commit()
    return TestingSession


@pytest.fixture()
def client(session_factory):
    def override_db():
        with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    yield TestClient(app, headers={"User-Agent": BROWSER_UA})
    app.dependency_overrides.clear()


def _counts(session_factory) -> dict[str, int]:
    with session_factory() as db:
        return {row.event: row.count for row in db.scalars(select(UsageDailyCount)).all()}


def test_record_usage_increments_one_row_per_day_and_event(session_factory):
    with session_factory() as db:
        for _ in range(3):
            record_usage(db, _request(BROWSER_UA), MODULES_VIEW, today=date(2026, 10, 14))
        record_usage(db, _request(BROWSER_UA), MODULES_VIEW, today=date(2026, 10, 15))
        rows = db.scalars(select(UsageDailyCount).order_by(UsageDailyCount.day)).all()

    assert [(row.day, row.count) for row in rows] == [(date(2026, 10, 14), 3), (date(2026, 10, 15), 1)]


@pytest.mark.parametrize("user_agent", ["", "curl/8.5.0", "Uptime-Kuma/1.23.16", "Mozilla/5.0 (compatible; Googlebot/2.1)"])
def test_record_usage_ignores_automated_clients(session_factory, user_agent):
    with session_factory() as db:
        record_usage(db, _request(user_agent), MODULES_VIEW)

    assert _counts(session_factory) == {}


def test_record_usage_survives_a_concurrent_first_insert(session_factory):
    """If another worker inserts today's row between our update and insert, we still count once more."""

    today = date(2026, 10, 14)
    with session_factory() as db, session_factory() as other:
        original_execute = db.execute
        calls = {"n": 0}

        def racing_execute(statement, *args, **kwargs):
            result = original_execute(statement, *args, **kwargs)
            calls["n"] += 1
            if calls["n"] == 1:
                other.add(UsageDailyCount(day=today, event=MODULES_VIEW, count=1))
                other.commit()
            return result

        db.execute = racing_execute
        record_usage(db, _request(BROWSER_UA), MODULES_VIEW, today=today)

    assert _counts(session_factory) == {MODULES_VIEW: 2}


def test_public_routes_count_views_and_exports_separately(client, session_factory):
    assert client.get("/").status_code == 200
    assert client.get("/").status_code == 200
    assert client.get("/practiques").status_code == 200
    # A failed export must not be counted.
    assert client.post("/practiques/export", data={"payload": "{}"}).status_code == 400

    assert _counts(session_factory) == {MODULES_VIEW: 2, INTERNSHIP_VIEW: 1}


def test_usage_summary_rolls_up_recent_and_weekly_totals(session_factory):
    with session_factory() as db:
        db.add_all(
            [
                UsageDailyCount(day=date(2026, 10, 14), event=MODULES_VIEW, count=5),
                UsageDailyCount(day=date(2026, 10, 5), event=MODULES_VIEW, count=4),
                UsageDailyCount(day=date(2026, 8, 3), event=MODULES_VIEW, count=7),
                UsageDailyCount(day=date(2026, 10, 12), event=INTERNSHIP_EXPORT, count=2),
                UsageDailyCount(day=date(2026, 10, 12), event=MODULES_PLAN, count=1),
            ]
        )
        db.commit()
        summary = usage_summary(db, today=date(2026, 10, 14), weeks=3)

    assert summary["tracking_since"] == date(2026, 8, 3)
    assert summary["totals"][MODULES_VIEW] == {"last_7": 5, "last_30": 9, "all": 16}
    assert summary["totals"][INTERNSHIP_EXPORT] == {"last_7": 2, "last_30": 2, "all": 2}
    assert [week["week_start"] for week in summary["weekly"]] == [date(2026, 10, 12), date(2026, 10, 5), date(2026, 9, 28)]
    assert summary["weekly"][0]["counts"][MODULES_VIEW] == 5
    assert summary["weekly"][1]["counts"][MODULES_VIEW] == 4
    assert summary["weekly"][2]["counts"][MODULES_VIEW] == 0


def test_usage_page_requires_admin(client):
    response = client.get("/admin/usage", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/admin/login"


def test_usage_page_lists_both_tools(client, session_factory):
    client.get("/practiques")
    app.dependency_overrides[require_admin] = lambda: None

    response = client.get("/admin/usage")

    assert response.status_code == 200
    assert "Planificació de mòduls" in response.text
    assert "Calendari de pràctiques" in response.text
    assert "Dades des del" in response.text


def test_png_download_is_counted(client, session_factory):
    response = client.post("/practiques/export-png")

    assert response.status_code == 204
    assert _counts(session_factory) == {INTERNSHIP_EXPORT_PNG: 1}
