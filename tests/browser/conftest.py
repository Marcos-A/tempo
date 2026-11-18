"""Fixtures for the browser tests of the internship planner.

They run the real app in its own process, against a temporary database, and
drive it with Chromium. Each test gets a fresh browser context, so the draft
the page keeps in localStorage never leaks from one test to another.

Playwright is imported inside the fixtures: without it (requirements-dev.txt)
the tests in this folder skip and the rest of the suite is unaffected.
"""

from __future__ import annotations

import os
import re
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database import Base
from app.models import AcademicYear, ExcludedPeriod, RecurringHoliday

REPO_ROOT = Path(__file__).resolve().parents[2]
SERVER_START_SECONDS = 30

SCHOOL_PERIODS = (
    (date(2026, 12, 7), date(2026, 12, 7), "Lliure disposició"),
    (date(2026, 12, 22), date(2027, 1, 7), "Vacances de Nadal"),
    (date(2027, 2, 8), date(2027, 2, 8), "Lliure de febrer"),
    (date(2027, 3, 22), date(2027, 3, 29), "Vacances de Setmana Santa"),
    (date(2027, 4, 30), date(2027, 4, 30), "Lliure d'abril"),
    (date(2027, 5, 17), date(2027, 5, 17), "Segona pasqua"),
)
FIXED_HOLIDAYS = (
    (10, 12, "Festa Nacional"),
    (11, 1, "Tots Sants"),
    (12, 8, "Immaculada Concepció"),
    (12, 25, "Nadal"),
    (1, 1, "Any Nou"),
    (5, 1, "Festa del Treball"),
    (6, 24, "Sant Joan"),
    (8, 15, "Assumpció"),
)


def _seed(database_url: str) -> None:
    engine = create_engine(database_url)
    Base.metadata.create_all(bind=engine)
    with Session(engine) as db:
        year = AcademicYear(
            label="2026-27", default_start_date=date(2026, 9, 7), default_end_date=date(2027, 6, 18), is_active=True
        )
        db.add(year)
        db.flush()
        for start, end, label in SCHOOL_PERIODS:
            db.add(ExcludedPeriod(academic_year_id=year.id, start_date=start, end_date=end, label=label))
        for month, day, label in FIXED_HOLIDAYS:
            db.add(RecurringHoliday(month=month, day=day, label=label))
        db.commit()
    engine.dispose()


def _free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


@pytest.fixture(scope="session")
def base_url(tmp_path_factory):
    """Start the app on a free port with a seeded, throwaway database."""

    pytest.importorskip("playwright")
    data_dir = tmp_path_factory.mktemp("browser-data")
    database_url = f"sqlite:///{data_dir / 'app.db'}"
    _seed(database_url)
    port = _free_port()
    log_path = data_dir / "server.log"
    with log_path.open("w") as log:
        server = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(port)],
            cwd=REPO_ROOT,
            env={**os.environ, "DATABASE_URL": database_url, "SECRET_KEY": "browser-tests", "ADMIN_PASSWORD": "browser-tests"},
            stdout=log,
            stderr=subprocess.STDOUT,
        )
    url = f"http://127.0.0.1:{port}"
    try:
        deadline = time.monotonic() + SERVER_START_SECONDS
        while True:
            try:
                urllib.request.urlopen(f"{url}/practiques", timeout=2).read()
                break
            except (urllib.error.URLError, OSError):
                if server.poll() is not None or time.monotonic() > deadline:
                    pytest.fail(f"The test server did not start:\n{log_path.read_text()}")
                time.sleep(0.1)
        yield url
    finally:
        server.terminate()
        server.wait(timeout=10)


@pytest.fixture(scope="session")
def browser():
    sync_api = pytest.importorskip("playwright.sync_api")
    with sync_api.sync_playwright() as playwright:
        chromium = playwright.chromium.launch()
        yield chromium
        chromium.close()


class Planner:
    """What a user does on /practiques, and what they then see.

    Assertions use Playwright's `expect`, which retries until the page shows
    the value, so the tests wait for the recalculation rather than for a time.
    """

    def __init__(self, page, base_url: str):
        from playwright.sync_api import expect

        self.page = page
        self.base_url = base_url
        self._expect = expect

    def open(self) -> None:
        self.page.goto(f"{self.base_url}/practiques")

    def another_user(self) -> Planner:
        """A second user with their own browser data, closed along with this one's."""

        user = Planner(self.page.context.browser.new_context().new_page(), self.base_url)
        self.page.context.on("close", lambda _: user.page.context.close())
        user.open()
        return user

    def fill(self, *, start: str, hours: int, end: str, daily_hours: int = 4) -> None:
        """Fill in the basics; `end` is what the page must then show, so the plan has settled."""

        self.page.fill("#start-date", start)
        self.page.fill("#target-hours", str(hours))
        for weekday in range(5):
            self.page.select_option(f'[data-weekday-hours="{weekday}"]', str(daily_hours))
        self.expect_end(end)

    # Actions

    def set_day(self, iso: str, hours: int) -> None:
        self.day(iso).click()
        self.page.select_option("#day-editor-hours", str(hours))
        self.page.locator('#day-editor button[value="save"]').click()

    def add_day_off(self, start: str, end: str = "") -> None:
        self.page.fill("#extra-start", start)
        self.page.fill("#extra-end", end)
        self.page.locator("#extra-add").click()

    def remove_first_day_off(self) -> None:
        self.page.locator("#extra-period-list button").first.click()

    def period(self, label: str):
        return self.page.locator(f'li[data-period-label="{label}"] input')

    def fixed_holiday(self, iso: str):
        return self.page.locator(f'[data-fixed-date="{iso}"]')

    def choose_modality(self, value: str) -> None:
        # The radio itself is hidden; users click its label.
        self.page.locator(f"label.segmented-option:has(input[value={value}])").click()

    # What the page shows

    def day(self, iso: str):
        return self.page.locator(f'#month-grid [data-date="{iso}"]')

    def listed_fixed_holidays(self) -> set[str]:
        boxes = self.page.locator("[data-fixed-date]")
        return {boxes.nth(index).get_attribute("data-fixed-date") for index in range(boxes.count())}

    def expect_end(self, text: str) -> None:
        self._expect(self.page.locator("#summary-end")).to_have_text(text)

    def expect_hours(self, text: str) -> None:
        self._expect(self.page.locator("#summary-hours")).to_have_text(text)

    def expect_changed_days(self, count: int) -> None:
        self._expect(self.page.locator("#summary-overrides")).to_have_text(str(count))

    def expect_day(self, iso: str, kind: str, hours: str) -> None:
        cell = self.day(iso)
        self._expect(cell).to_have_class(re.compile(rf"\bday-{kind}\b"))
        self._expect(cell.locator(".month-day-hours")).to_have_text(hours)

    def expect_note(self, text: str | None) -> None:
        note = self.page.locator("#days-off-note")
        if text is None:
            self._expect(note).to_be_hidden()
        else:
            self._expect(note).to_have_text(text)


@pytest.fixture(scope="session")
def fixed_holiday_labels():
    return {label for _, _, label in FIXED_HOLIDAYS}


@pytest.fixture()
def planner(browser, base_url):
    """A fresh user on the planner; any uncaught script error fails the test."""

    context = browser.new_context(viewport={"width": 1400, "height": 1000}, accept_downloads=True)
    page = context.new_page()
    errors: list[str] = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    user = Planner(page, base_url)
    user.open()
    yield user
    context.close()
    assert not errors, f"Script errors on the page: {errors}"
