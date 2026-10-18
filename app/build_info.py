"""Build and release identification for the deployed app.

The deploy script captures the commit SHA on the host and bakes it into the
image (`GIT_COMMIT`, `BUILD_TIME`). The environment (`APP_ENV`) and the
repository URL are runtime settings, so the same image can be promoted.
The latest published release is read from `release-info.json`, which
`scripts/update-release-info.sh` writes on the host; it is re-read on every
call so publishing a release does not need a rebuild.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

SHA_PATTERN = re.compile(r"^[0-9a-f]{40}$")
DEFAULT_BUILD_META_DIR = "build-meta"


def _read_release() -> dict | None:
    """Return the published release metadata, or None when it cannot be trusted."""

    path = Path(os.getenv("BUILD_META_DIR", DEFAULT_BUILD_META_DIR)) / "release-info.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict) or not all(isinstance(data.get(key), str) and data[key] for key in ("version", "tag", "commit")):
        return None
    return {"version": data["version"], "tag": data["tag"], "commit": data["commit"]}


def get_build_info() -> dict:
    """Return the standard build-info schema for this deployment."""

    sha = os.getenv("GIT_COMMIT", "").strip().lower()
    build: dict | None = None
    if SHA_PATTERN.match(sha):
        build = {"sha": sha, "shortSha": sha[:7]}
        built_at = os.getenv("BUILD_TIME", "").strip()
        if built_at:
            build["builtAt"] = built_at
    info = {
        "schemaVersion": 1,
        "app": "tempo",
        "environment": os.getenv("APP_ENV", "").strip() or None,
        "build": build,
        "release": _read_release(),
    }
    repo_url = os.getenv("REPO_URL", "").strip().rstrip("/")
    if repo_url:
        info["repository"] = repo_url
    return info


def build_footer(info: dict | None = None) -> dict | None:
    """Return the footer label and links, or None when build info is not configured.

    Deployments without `APP_ENV` (local development, or a production setup that
    has not been wired yet) show no footer at all.
    """

    info = info or get_build_info()
    environment = info["environment"]
    if not environment:
        return None

    build = info["build"]
    release = info["release"] if environment == "production" else None
    repo_url = info.get("repository")
    parts: list[dict] = []
    if environment == "preview":
        parts.append({"text": "Preview", "href": None})
    elif release:
        parts.append({"text": release["tag"], "href": f"{repo_url}/releases/tag/{release['tag']}" if repo_url else None})
    elif build:
        parts.append({"text": "Build", "href": None})

    if build:
        parts.append({"text": build["shortSha"], "href": f"{repo_url}/commit/{build['sha']}" if repo_url else None})
    else:
        parts.append({"text": "Build unknown", "href": None})

    details = [f"Entorn: {environment}"]
    if release:
        details.append(f"Última versió publicada: {release['tag']}")
    details.append(f"Commit desplegat: {build['sha'] if build else 'desconegut'}")
    return {"parts": parts, "title": "\n".join(details)}
