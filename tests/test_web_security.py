"""Tests for script-injection protection and session cookie settings."""

import json
import re

import pytest

from app.config import get_settings
from tests.test_internship import client  # noqa: F401  (pytest fixture)

MARKER = "</script><b id=injected>x</b>"


def test_submitted_plan_cannot_close_the_inline_script(client):  # noqa: F811
    """The plan is echoed back on a validation error, and must stay inside its script block."""

    test_client, _ = client
    plan = {"schedule": [], "blocks": [], "planning_mode": "sequential", "total_available_hours": 1, "note": MARKER}
    response = test_client.post(
        "/export",
        data={
            "plan_json": json.dumps(plan),
            "ra_order": "[]",
            "ra_names": json.dumps({"x": MARKER}),
            "ra_hours": "{}",
        },
    )

    assert response.status_code == 400
    assert MARKER not in response.text
    embedded = re.search(r'<script id="plan-data" type="application/json">(.*?)</script>', response.text, re.S)
    assert json.loads(embedded.group(1))["note"] == MARKER


@pytest.mark.parametrize(
    ("app_env", "expected"),
    [("production", True), ("preview", True), ("", False)],
)
def test_session_cookie_is_secure_only_when_deployed(monkeypatch, app_env, expected):
    monkeypatch.setenv("APP_ENV", app_env)

    assert get_settings().cookie_secure is expected


def test_admin_login_is_throttled_after_repeated_failures(client):  # noqa: F811
    from app.routes.admin import login_throttle

    test_client, _ = client
    login_throttle._failures.clear()
    for _ in range(10):
        assert test_client.post("/admin/login", data={"username": "a", "password": "b"}).status_code == 400

    assert test_client.post("/admin/login", data={"username": "a", "password": "b"}).status_code == 429
    login_throttle._failures.clear()


def test_api_docs_are_not_exposed(client):  # noqa: F811
    test_client, _ = client
    for path in ("/docs", "/redoc", "/openapi.json"):
        assert test_client.get(path).status_code == 404
