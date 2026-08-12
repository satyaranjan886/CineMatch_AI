#!/usr/bin/env python3
"""Measure latency for key API endpoints. Records only real timings.

Usage (from repo root):
  DJANGO_SETTINGS_MODULE=config.settings.development \\
    .venv/bin/python scripts/perf_benchmark.py [--rounds 30] [--output /tmp/perf-results.md]
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND = REPO_ROOT / "backend"
sys.path.insert(0, str(BACKEND))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

import django

django.setup()

from django.conf import settings
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.movies.models import Movie, MovieStatus
from apps.search.models import MovieEmbedding
from apps.search.services.embeddings import MovieEmbeddingService

User = get_user_model()


def _ensure_embedding_provider() -> str:
    """Use the configured provider when available; otherwise fall back to mock."""
    try:
        import sentence_transformers  # noqa: F401

        return settings.EMBEDDING_PROVIDER_CLASS
    except ImportError:
        settings.EMBEDDING_PROVIDER_CLASS = "ml.embeddings.mock.MockEmbeddingProvider"
        return settings.EMBEDDING_PROVIDER_CLASS


def _ensure_embeddings() -> int:
    service = MovieEmbeddingService()
    existing = MovieEmbedding.objects.filter(
        model_name=service.model_name,
        model_version=service.model_version,
    ).count()
    if existing > 0:
        return existing
    movies = list(Movie.objects.filter(status=MovieStatus.RELEASED).with_catalog_relations())
    result = service.generate_for_movies(movies)
    return result.created + result.updated


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(round((pct / 100) * (len(ordered) - 1)))))
    return ordered[index]


def _summarize(name: str, samples_ms: list[float], status_codes: list[int]) -> dict:
    return {
        "endpoint": name,
        "rounds": len(samples_ms),
        "status_codes": sorted(set(status_codes)),
        "mean_ms": round(statistics.fmean(samples_ms), 2) if samples_ms else None,
        "p50_ms": round(_percentile(samples_ms, 50), 2) if samples_ms else None,
        "p95_ms": round(_percentile(samples_ms, 95), 2) if samples_ms else None,
        "min_ms": round(min(samples_ms), 2) if samples_ms else None,
        "max_ms": round(max(samples_ms), 2) if samples_ms else None,
    }


def _time_get(client: APIClient, path: str) -> tuple[float, int]:
    started = time.perf_counter()
    response = client.get(path)
    elapsed_ms = (time.perf_counter() - started) * 1000.0
    return elapsed_ms, response.status_code


def main() -> int:
    parser = argparse.ArgumentParser(description="CineMatch API performance benchmark")
    parser.add_argument("--rounds", type=int, default=25)
    parser.add_argument(
        "--output",
        type=Path,
        default=REPO_ROOT / "loadtests" / "results" / "perf-benchmark.md",
    )
    args = parser.parse_args()

    provider = _ensure_embedding_provider()
    embedding_count = _ensure_embeddings()

    password = "perf-pass-12345"
    user, _ = User.objects.get_or_create(
        email="perf-bench@example.com",
        defaults={"is_active": True},
    )
    user.set_password(password)
    user.save()

    movie = Movie.objects.filter(status=MovieStatus.RELEASED).order_by("-popularity").first()
    if movie is None:
        print("No released movies found. Seed the catalog before benchmarking.", file=sys.stderr)
        return 1

    client = APIClient()
    client.raise_request_exception = False
    login = client.post(
        "/api/v1/auth/login/",
        {"email": user.email, "password": password},
        format="json",
    )
    if login.status_code != 200:
        print(f"Login failed: {login.status_code} {login.data}", file=sys.stderr)
        return 1
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")

    targets = [
        ("GET /api/v1/recommendations/home/", "/api/v1/recommendations/home/"),
        ("GET /api/v1/movies/{id}/", f"/api/v1/movies/{movie.id}/"),
        ("GET /api/v1/search/semantic/?q=...", "/api/v1/search/semantic/?q=space%20adventure&limit=10"),
    ]

    # Warm-up (not recorded)
    for _, path in targets:
        client.get(path)

    results = []
    for label, path in targets:
        samples: list[float] = []
        codes: list[int] = []
        for _ in range(args.rounds):
            elapsed_ms, code = _time_get(client, path)
            samples.append(elapsed_ms)
            codes.append(code)
        results.append(_summarize(label, samples, codes))

    measured_at = datetime.now(timezone.utc).isoformat()
    payload = {
        "measured_at_utc": measured_at,
        "rounds_per_endpoint": args.rounds,
        "settings_module": os.environ["DJANGO_SETTINGS_MODULE"],
        "embedding_provider": provider,
        "embedding_rows": embedding_count,
        "movie_id": str(movie.id),
        "results": results,
    }

    lines = [
        "# Performance benchmark results",
        "",
        "Generated by `scripts/perf_benchmark.py`. Values are measured, not estimated.",
        "",
        f"- Measured at (UTC): `{measured_at}`",
        f"- Settings: `{os.environ['DJANGO_SETTINGS_MODULE']}`",
        f"- Embedding provider: `{provider}`",
        f"- Embedding rows available: `{embedding_count}`",
        f"- Rounds per endpoint: `{args.rounds}`",
        f"- Movie fixture id: `{movie.id}`",
        "",
        "| Endpoint | Rounds | Status | Mean ms | p50 ms | p95 ms | Min ms | Max ms |",
        "| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in results:
        lines.append(
            "| {endpoint} | {rounds} | {status} | {mean_ms} | {p50_ms} | {p95_ms} | {min_ms} | {max_ms} |".format(
                endpoint=row["endpoint"],
                rounds=row["rounds"],
                status=",".join(str(code) for code in row["status_codes"]),
                mean_ms=row["mean_ms"],
                p50_ms=row["p50_ms"],
                p95_ms=row["p95_ms"],
                min_ms=row["min_ms"],
                max_ms=row["max_ms"],
            )
        )
    lines.extend(
        [
            "",
            "## Notes",
            "",
            "- Timings include Django view/ORM/cache work via `APIClient` (no HTTP server hop).",
            "- If `sentence_transformers` is not installed, the script falls back to "
            "`MockEmbeddingProvider` and records that in metadata above.",
            "",
            "## Raw JSON",
            "",
            "```json",
            json.dumps(payload, indent=2),
            "```",
            "",
        ]
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {args.output}")
    for row in results:
        print(
            f"{row['endpoint']}: mean={row['mean_ms']}ms p50={row['p50_ms']}ms "
            f"p95={row['p95_ms']}ms status={row['status_codes']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
