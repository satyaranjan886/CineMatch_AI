#!/usr/bin/env python3
"""Evaluate Locust CSV stats against configured thresholds.

Exit 0 only when measured metrics meet thresholds (not merely because Locust finished).
"""

from __future__ import annotations

import argparse
import csv
import json
from datetime import UTC, datetime
from pathlib import Path


def _load_stats(stats_csv: Path) -> dict[str, dict]:
    rows = {}
    with stats_csv.open() as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            name = row.get("Name") or row.get("name")
            if not name:
                continue
            rows[name] = row
    return rows


def _f(row: dict, *keys: str) -> float:
    for key in keys:
        if key in row and row[key] not in (None, ""):
            return float(row[key])
    return 0.0


def evaluate(stats_csv: Path, thresholds_path: Path) -> tuple[bool, dict]:
    thresholds = json.loads(thresholds_path.read_text())["thresholds"]
    rows = _load_stats(stats_csv)

    # Prefer HTTP endpoints only when summarizing overall RPS/error (exclude custom rows).
    http_rows = [
        row
        for name, row in rows.items()
        if name != "Aggregated"
        and (
            name.startswith("GET ")
            or name.startswith("POST ")
            or name.startswith("PUT ")
            or name.startswith("DELETE ")
            or name.startswith("PATCH ")
        )
    ]
    if http_rows:
        request_count = sum(_f(r, "Request Count") for r in http_rows)
        failure_count = sum(_f(r, "Failure Count") for r in http_rows)
        requests_per_sec = sum(_f(r, "Requests/s") for r in http_rows)
    else:
        aggregated = rows.get("Aggregated") or rows.get("Total")
        if not aggregated:
            raise SystemExit(f"No Aggregated row in {stats_csv}")
        request_count = _f(aggregated, "Request Count")
        failure_count = _f(aggregated, "Failure Count")
        requests_per_sec = _f(aggregated, "Requests/s")

    error_rate = (failure_count / request_count * 100.0) if request_count else 100.0

    home = rows.get("GET /api/v1/recommendations/home/", {})
    movies = rows.get("GET /api/v1/movies/", {})
    detail = rows.get("GET /api/v1/movies/{id}/", {})
    search = rows.get("GET /api/v1/search/semantic/", {}) or rows.get(
        "GET /api/v1/search/", {}
    )

    measured = {
        "request_count": request_count,
        "failure_count": failure_count,
        "error_rate_pct": round(error_rate, 3),
        "requests_per_sec": requests_per_sec,
        "p50_ms": _f(home, "50%", "Median Response Time"),
        "p95_ms": _f(home, "95%", "95%"),
        "p99_ms": _f(home, "99%", "99%"),
        "home_p95_ms": _f(home, "95%", "95%"),
        "home_p99_ms": _f(home, "99%", "99%"),
        "movies_list_p95_ms": _f(movies, "95%", "95%"),
        "movie_detail_p95_ms": _f(detail, "95%", "95%"),
        "search_p95_ms": _f(search, "95%", "95%"),
    }

    checks = {
        "error_rate": measured["error_rate_pct"] <= thresholds["error_rate_pct_max"],
        "home_p95": measured["home_p95_ms"] <= thresholds["p95_home_ms_max"],
        "home_p99": measured["home_p99_ms"] <= thresholds["p99_home_ms_max"],
        "movies_list_p95": measured["movies_list_p95_ms"] <= thresholds["p95_movies_list_ms_max"],
        "movie_detail_p95": measured["movie_detail_p95_ms"] <= thresholds["p95_movie_detail_ms_max"],
        "search_p95": measured["search_p95_ms"] <= thresholds["p95_search_ms_max"],
    }
    passed = all(checks.values())
    return passed, {
        "evaluated_at_utc": datetime.now(tz=UTC).isoformat(),
        "thresholds": thresholds,
        "measured": measured,
        "checks": checks,
        "accepted": passed,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stats-csv", type=Path, required=True)
    parser.add_argument(
        "--thresholds",
        type=Path,
        default=Path("loadtests/config/thresholds.json"),
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    passed, report = evaluate(args.stats_csv, args.thresholds)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))
    if not passed:
        print("ACCEPTANCE: FAILED (thresholds not met)")
        return 1
    print("ACCEPTANCE: PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
