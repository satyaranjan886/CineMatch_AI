"""Locust HTTP load tests for CineMatch AI.

Measures real network + WSGI/ASGI latency. Do NOT confuse with
scripts/perf_benchmark.py (in-process APIClient timings).

Usage:
  locust -f loadtests/locustfile.py --host http://127.0.0.1:8000 \\
    --users 50 --spawn-rate 5 --run-time 2m --headless \\
    --csv loadtests/results/baseline_low --html loadtests/results/baseline_low.html
"""

from __future__ import annotations

import json
import os
import random
from pathlib import Path
from typing import Any

from locust import HttpUser, between, events, task
from locust.runners import MasterRunner


LOADTEST_PASSWORD = os.getenv("LOADTEST_PASSWORD", "LoadTestPass123!")
LOADTEST_USER_PREFIX = os.getenv("LOADTEST_USER_PREFIX", "loadtest-user-")
LOADTEST_EMAIL_DOMAIN = os.getenv("LOADTEST_EMAIL_DOMAIN", "loadtest.cinematch.local")
LOADTEST_USER_COUNT = int(os.getenv("LOADTEST_USER_COUNT", "50"))
SEARCH_QUERIES = [
    "space",
    "love",
    "war",
    "comedy",
    "mission",
    "Loadtest",
]

# Side-channel stage timings (do NOT fire Locust request events — that pollutes Aggregated).
_STAGE_SAMPLES: dict[str, list[float]] = {}
_CACHE_COUNTS = {"HIT": 0, "MISS": 0, "UNKNOWN": 0}


def _parse_timing_header(value: str | None) -> dict[str, float]:
    if not value:
        return {}
    out: dict[str, float] = {}
    for part in value.split(";"):
        if "=" not in part:
            continue
        key, raw = part.split("=", 1)
        try:
            out[key.strip()] = float(raw.strip())
        except ValueError:
            continue
    return out


def _percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    rank = (pct / 100.0) * (len(ordered) - 1)
    low = int(rank)
    high = min(low + 1, len(ordered) - 1)
    weight = rank - low
    return ordered[low] * (1 - weight) + ordered[high] * weight


def _record_stage_timings(timings: dict[str, float], cache_state: str) -> None:
    bucket = cache_state if cache_state in _CACHE_COUNTS else "UNKNOWN"
    _CACHE_COUNTS[bucket] += 1
    for key, value_ms in timings.items():
        _STAGE_SAMPLES.setdefault(key, []).append(value_ms)


class CineMatchUser(HttpUser):
    """Authenticated browser-like mix with emphasis on personalized home."""

    wait_time = between(0.5, 2.0)
    movie_ids: list[str] = []

    def on_start(self) -> None:
        index = random.randint(0, max(LOADTEST_USER_COUNT - 1, 0))
        email = f"{LOADTEST_USER_PREFIX}{index}@{LOADTEST_EMAIL_DOMAIN}"
        with self.client.post(
            "/api/v1/auth/login/",
            json={"email": email, "password": LOADTEST_PASSWORD},
            name="POST /api/v1/auth/login/",
            catch_response=True,
        ) as response:
            if response.status_code != 200:
                response.failure(f"login failed: {response.status_code}")
                self.access_token = None
                return
            payload = response.json()
            self.access_token = payload.get("access")
            if not self.access_token:
                response.failure("login response missing access token")
                return
            response.success()

        self.client.headers.update({"Authorization": f"Bearer {self.access_token}"})
        listing = self.client.get("/api/v1/movies/?page_size=20", name="GET /api/v1/movies/ (warmup)")
        if listing.status_code == 200:
            results = listing.json().get("results") or listing.json().get("movies") or []
            self.movie_ids = [str(item.get("id")) for item in results if item.get("id")]

    @task(5)
    def home_recommendations(self) -> None:
        if not getattr(self, "access_token", None):
            return
        with self.client.get(
            "/api/v1/recommendations/home/",
            name="GET /api/v1/recommendations/home/",
            catch_response=True,
        ) as response:
            if response.status_code != 200:
                response.failure(f"home status {response.status_code}")
                return
            timings = _parse_timing_header(response.headers.get("X-Cinematch-Timing"))
            cache_state = response.headers.get("X-Cinematch-Cache", "UNKNOWN")
            _record_stage_timings(timings, cache_state)
            response.success()

    @task(3)
    def movies_list(self) -> None:
        page = random.randint(1, 5)
        self.client.get(f"/api/v1/movies/?page={page}", name="GET /api/v1/movies/")

    @task(3)
    def movie_detail(self) -> None:
        if not self.movie_ids:
            listing = self.client.get("/api/v1/movies/?page_size=20", name="GET /api/v1/movies/")
            if listing.status_code == 200:
                results = listing.json().get("results") or []
                self.movie_ids = [str(item.get("id")) for item in results if item.get("id")]
        if not self.movie_ids:
            return
        movie_id = random.choice(self.movie_ids)
        self.client.get(f"/api/v1/movies/{movie_id}/", name="GET /api/v1/movies/{id}/")

    @task(2)
    def search(self) -> None:
        query = random.choice(SEARCH_QUERIES)
        # Catalog search surface used by the product (semantic search API).
        self.client.get(
            f"/api/v1/search/semantic/?q={query}&limit=10",
            name="GET /api/v1/search/semantic/",
        )


@events.init.add_listener
def on_locust_init(environment, **_kwargs: Any) -> None:
    if isinstance(environment.runner, MasterRunner):
        return
    print(
        "CineMatch Locust load test initialized. "
        "Target only local/staging hosts — never public production."
    )


@events.quitting.add_listener
def on_locust_quitting(environment, **_kwargs: Any) -> None:
    """Write recommendation stage timing summary next to Locust CSV prefix."""
    csv_prefix = getattr(environment.parsed_options, "csv_prefix", None)
    if not csv_prefix:
        return
    summary: dict[str, Any] = {
        "cache_counts": dict(_CACHE_COUNTS),
        "stages_ms": {},
    }
    for key, samples in sorted(_STAGE_SAMPLES.items()):
        summary["stages_ms"][key] = {
            "n": len(samples),
            "avg": round(sum(samples) / len(samples), 2) if samples else None,
            "p50": round(_percentile(samples, 50) or 0, 2),
            "p95": round(_percentile(samples, 95) or 0, 2),
            "p99": round(_percentile(samples, 99) or 0, 2),
            "max": round(max(samples), 2) if samples else None,
        }
    out = Path(f"{csv_prefix}_rec_stages.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=2))
    print(f"Wrote recommendation stage summary: {out}")
