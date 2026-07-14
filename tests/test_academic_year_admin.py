"""Tests for the academic-year management model and admin safeguards."""

import sqlite3
from datetime import date
from pathlib import Path

from starlette.requests import Request
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import sessionmaker

from app.database import Base, _configure_sqlite_connection
from app.main import app
from app.models import AcademicWeekNumber, AcademicYear, ExcludedPeriod
from app.routes import admin as admin_routes
from app.services.bootstrap import bootstrap_database


def _legacy_engine(db_path: Path):
    """Build a dedicated SQLite engine for migration-style tests."""

    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    event.listen(engine, "connect", _configure_sqlite_connection)
    return engine


def _request(path: str, query_string: bytes = b"") -> Request:
    """Build a minimal Starlette request for direct route-function tests."""

    return Request({"type": "http", "method": "POST", "path": path, "headers": [], "query_string": query_string, "app": app, "router": app.router})


def test_bootstrap_migrates_legacy_years_and_assigns_existing_records(tmp_path, monkeypatch):
    """Legacy singleton/archive data should become first-class academic years."""

    db_path = tmp_path / "planner.db"
    monkeypatch.setenv("ADMIN_USERNAME", "admin")
    monkeypatch.setenv("ADMIN_PASSWORD", "preview-secret")

    connection = sqlite3.connect(db_path)
    connection.executescript(
        """
        CREATE TABLE academic_year_settings (
            id INTEGER PRIMARY KEY,
            label VARCHAR(50),
            default_start_date DATE NOT NULL,
            default_end_date DATE NOT NULL,
            include_week_numbers_in_export BOOLEAN NOT NULL DEFAULT 0
        );
        CREATE TABLE academic_year_archive (
            id INTEGER PRIMARY KEY,
            label VARCHAR(50) NOT NULL,
            start_date DATE NOT NULL,
            end_date DATE NOT NULL,
            archived_at DATETIME
        );
        CREATE TABLE excluded_periods (
            id INTEGER PRIMARY KEY,
            start_date DATE NOT NULL,
            end_date DATE NOT NULL,
            label VARCHAR(255),
            created_at DATETIME
        );
        CREATE TABLE academic_week_numbers (
            id INTEGER PRIMARY KEY,
            week_start_date DATE UNIQUE NOT NULL,
            number INTEGER NOT NULL
        );
        INSERT INTO academic_year_settings (id, label, default_start_date, default_end_date, include_week_numbers_in_export)
        VALUES (1, '2026-27', '2026-09-01', '2027-06-30', 1);
        INSERT INTO academic_year_archive (id, label, start_date, end_date)
        VALUES (1, '2025-26', '2025-09-01', '2026-06-30');
        INSERT INTO excluded_periods (id, start_date, end_date, label)
        VALUES
          (1, '2025-12-22', '2026-01-07', 'Nadal 2025'),
          (2, '2026-12-22', '2027-01-07', 'Nadal 2026');
        INSERT INTO academic_week_numbers (id, week_start_date, number)
        VALUES
          (1, '2025-09-01', 1),
          (2, '2026-08-31', 1);
        """
    )
    connection.commit()
    connection.close()

    engine = _legacy_engine(db_path)
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)

    with SessionLocal() as session:
        bootstrap_database(session)

        academic_years = session.scalars(select(AcademicYear).order_by(AcademicYear.default_start_date)).all()
        assert [year.label for year in academic_years] == ["2025-26", "2026-27"]
        assert [year.is_active for year in academic_years] == [False, True]
        assert academic_years[1].include_week_numbers_in_export is True

        periods = session.scalars(select(ExcludedPeriod).order_by(ExcludedPeriod.id)).all()
        assert [period.academic_year_id for period in periods] == [academic_years[0].id, academic_years[1].id]

        weeks = session.scalars(select(AcademicWeekNumber).order_by(AcademicWeekNumber.id)).all()
        assert [week.academic_year_id for week in weeks] == [academic_years[0].id, academic_years[1].id]


def test_delete_year_requires_explicit_confirmation(tmp_path, monkeypatch):
    """The admin delete route should warn and refuse silent academic-year deletion."""

    db_path = tmp_path / "planner.db"
    monkeypatch.setenv("ADMIN_USERNAME", "admin")
    monkeypatch.setenv("ADMIN_PASSWORD", "preview-secret")

    engine = _legacy_engine(db_path)
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)

    with SessionLocal() as session:
        session.add_all(
            [
                AcademicYear(
                    label="2025-26",
                    default_start_date=date(2025, 9, 1),
                    default_end_date=date(2026, 6, 30),
                    include_week_numbers_in_export=False,
                    is_active=False,
                ),
                AcademicYear(
                    label="2026-27",
                    default_start_date=date(2026, 9, 1),
                    default_end_date=date(2027, 6, 30),
                    include_week_numbers_in_export=True,
                    is_active=True,
                ),
            ]
        )
        session.commit()
        inactive_year = session.scalar(select(AcademicYear).where(AcademicYear.label == "2025-26"))

        response = admin_routes.delete_year(_request(f"/admin/years/{inactive_year.id}/delete"), inactive_year.id, None, session, object())

        assert response.status_code == 400
        assert response.context["error"] == "Marca la confirmació abans de suprimir aquest curs."
        assert session.get(AcademicYear, inactive_year.id) is not None
