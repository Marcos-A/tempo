"""Tests for low-complexity runtime hardening choices."""

import sqlite3

import pytest

from app.database import _configure_sqlite_connection
from app.server import resolve_web_concurrency


def test_sqlite_connection_uses_concurrency_friendly_pragmas(tmp_path):
    """File-backed SQLite connections should enable the configured PRAGMAs."""

    connection = sqlite3.connect(tmp_path / "planner.db")
    _configure_sqlite_connection(connection, None)

    assert connection.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
    assert connection.execute("PRAGMA synchronous").fetchone()[0] == 1
    assert connection.execute("PRAGMA busy_timeout").fetchone()[0] == 5000
    assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1

    connection.close()


def test_web_concurrency_defaults_to_one_worker_on_single_cpu(monkeypatch):
    """Single-core hosts should not spawn extra workers by default."""

    monkeypatch.delenv("WEB_CONCURRENCY", raising=False)
    monkeypatch.setattr("app.server.cpu_count", lambda: 1)

    assert resolve_web_concurrency() == 1


def test_web_concurrency_defaults_to_up_to_four_workers(monkeypatch):
    """Multi-core hosts should use a modest worker count without over-scaling."""

    monkeypatch.delenv("WEB_CONCURRENCY", raising=False)
    monkeypatch.setattr("app.server.cpu_count", lambda: 8)

    assert resolve_web_concurrency() == 4


def test_web_concurrency_honors_explicit_env(monkeypatch):
    """An explicit worker override should take priority over CPU heuristics."""

    monkeypatch.setenv("WEB_CONCURRENCY", "3")

    assert resolve_web_concurrency() == 3


def test_web_concurrency_rejects_invalid_values(monkeypatch):
    """Bad worker counts should fail fast during startup."""

    monkeypatch.setenv("WEB_CONCURRENCY", "0")

    with pytest.raises(ValueError):
        resolve_web_concurrency()
