#!/usr/bin/env python3
"""Small concurrent smoke test for the public teacher flow."""

from __future__ import annotations

import argparse
import statistics
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlencode
from urllib.request import Request, urlopen


def run_plan_request(base_url: str, timeout: float) -> float:
    """Submit one representative `/plan` request and return its latency."""

    payload = urlencode(
        {
            "start_date": "15/09/2025",
            "end_date": "30/09/2025",
            "monday_hours": "2",
            "tuesday_hours": "2",
            "wednesday_hours": "0",
            "thursday_hours": "0",
            "friday_hours": "0",
            "ra_count": "2",
            "planning_mode": "sequential",
        }
    ).encode()
    request = Request(
        f"{base_url.rstrip('/')}/plan",
        data=payload,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    started = time.perf_counter()
    with urlopen(request, timeout=timeout) as response:
        body = response.read().decode("utf-8", errors="replace")
        if "Pas 2 de 2" not in body:
            raise RuntimeError("Unexpected response body: step 2 marker not found.")
    return time.perf_counter() - started


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8091", help="Target base URL")
    parser.add_argument("--requests", type=int, default=24, help="Total number of requests to send")
    parser.add_argument("--concurrency", type=int, default=8, help="Number of concurrent workers")
    parser.add_argument("--timeout", type=float, default=15.0, help="Per-request timeout in seconds")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.requests < 1 or args.concurrency < 1:
        raise SystemExit("--requests and --concurrency must be at least 1")

    durations: list[float] = []
    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=args.concurrency) as executor:
        futures = [executor.submit(run_plan_request, args.base_url, args.timeout) for _ in range(args.requests)]
        for future in as_completed(futures):
            durations.append(future.result())
    total_elapsed = time.perf_counter() - started

    durations.sort()
    p95_index = max(0, min(len(durations) - 1, round(len(durations) * 0.95) - 1))
    print(f"base_url={args.base_url}")
    print(f"requests={args.requests}")
    print(f"concurrency={args.concurrency}")
    print(f"total_elapsed={total_elapsed:.3f}s")
    print(f"avg_latency={statistics.mean(durations):.3f}s")
    print(f"median_latency={statistics.median(durations):.3f}s")
    print(f"p95_latency={durations[p95_index]:.3f}s")
    print(f"max_latency={max(durations):.3f}s")
    print(f"throughput={args.requests / total_elapsed:.2f} req/s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
