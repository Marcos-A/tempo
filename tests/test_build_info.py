"""Tests for the build identification footer and endpoint."""

import json

from fastapi.testclient import TestClient

from app.build_info import build_footer, get_build_info
from app.main import app

SHA = "2ba5fcf9720ad1a287cf722158d49f9c54dea0a7"
REPO = "https://github.com/Marcos-A/tempo"


def configure(monkeypatch, tmp_path, *, env="preview", sha=SHA, release=None):
    monkeypatch.setenv("APP_ENV", env)
    monkeypatch.setenv("GIT_COMMIT", sha)
    monkeypatch.setenv("REPO_URL", REPO)
    monkeypatch.setenv("BUILD_META_DIR", str(tmp_path))
    monkeypatch.delenv("BUILD_TIME", raising=False)
    if release is not None:
        (tmp_path / "release-info.json").write_text(json.dumps(release))


def labels(footer):
    return " · ".join(part["text"] for part in footer["parts"])


def test_preview_shows_environment_and_short_sha(monkeypatch, tmp_path):
    configure(monkeypatch, tmp_path)
    footer = build_footer()

    assert labels(footer) == "Preview · 2ba5fcf"
    assert footer["parts"][1]["href"] == f"{REPO}/commit/{SHA}"


def test_production_shows_release_and_sha(monkeypatch, tmp_path):
    configure(monkeypatch, tmp_path, env="production", release={"version": "1.6.0", "tag": "v1.6.0", "commit": "abc"})
    footer = build_footer()

    assert labels(footer) == "v1.6.0 · 2ba5fcf"
    assert footer["parts"][0]["href"] == f"{REPO}/releases/tag/v1.6.0"


def test_production_without_release_shows_build(monkeypatch, tmp_path):
    configure(monkeypatch, tmp_path, env="production", release=None)

    assert labels(build_footer()) == "Build · 2ba5fcf"


def test_invalid_release_file_is_ignored(monkeypatch, tmp_path):
    configure(monkeypatch, tmp_path, env="production")
    (tmp_path / "release-info.json").write_text("null")

    assert get_build_info()["release"] is None


def test_missing_sha_falls_back_to_unknown(monkeypatch, tmp_path):
    configure(monkeypatch, tmp_path, sha="not-a-sha")

    assert get_build_info()["build"] is None
    assert labels(build_footer()) == "Preview · Build unknown"


def test_no_footer_without_environment(monkeypatch, tmp_path):
    configure(monkeypatch, tmp_path)
    monkeypatch.delenv("APP_ENV")

    assert build_footer() is None


def test_endpoint_returns_schema_without_caching(monkeypatch, tmp_path):
    configure(monkeypatch, tmp_path)
    response = TestClient(app).get("/build-info.json")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-cache"
    body = response.json()
    assert body["schemaVersion"] == 1
    assert body["environment"] == "preview"
    assert body["build"] == {"sha": SHA, "shortSha": "2ba5fcf"}
