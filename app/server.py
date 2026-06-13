"""Runtime entrypoint for the production-style web server."""

from __future__ import annotations

import os
from multiprocessing import cpu_count

import uvicorn


def resolve_web_concurrency() -> int:
    """Return a conservative worker count suitable for this small app."""

    configured = os.getenv("WEB_CONCURRENCY", "").strip()
    if configured:
        workers = int(configured)
        if workers < 1:
            raise ValueError("WEB_CONCURRENCY must be at least 1.")
        return workers

    available_cpus = cpu_count() or 1
    if available_cpus <= 1:
        return 1
    return min(4, available_cpus)


def main() -> None:
    """Start the application with a modest multi-worker default."""

    uvicorn.run(
        "app.main:app",
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8000")),
        proxy_headers=True,
        forwarded_allow_ips="*",
        workers=resolve_web_concurrency(),
    )


if __name__ == "__main__":
    main()
