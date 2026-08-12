#!/usr/bin/env python3
"""Sample host metrics during a Locust run (CPU, memory, Redis, Postgres, Celery)."""

from __future__ import annotations

import argparse
import json
import os
import time
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

import psutil


def _redis_ping(redis_url: str) -> dict:
    try:
        import redis
    except ImportError:
        return {"ok": False, "error": "redis package missing"}
    client = redis.Redis.from_url(redis_url, socket_connect_timeout=1, socket_timeout=1)
    started = time.perf_counter()
    pong = client.ping()
    latency_ms = (time.perf_counter() - started) * 1000
    depth = None
    try:
        # Celery default queue when using Redis broker DB.
        depth = int(client.llen("celery") or 0)
    except Exception:  # noqa: BLE001
        depth = None
    return {"ok": bool(pong), "latency_ms": round(latency_ms, 2), "celery_queue_depth": depth}


def _postgres_connections(database_url: str) -> dict:
    try:
        import psycopg
    except ImportError:
        return {"ok": False, "error": "psycopg missing"}
    try:
        with psycopg.connect(database_url, connect_timeout=2) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT count(*) FROM pg_stat_activity WHERE datname = current_database()"
                )
                total = int(cur.fetchone()[0])
                cur.execute(
                    "SELECT count(*) FROM pg_stat_activity "
                    "WHERE datname = current_database() AND state = 'active'"
                )
                active = int(cur.fetchone()[0])
        return {"ok": True, "total": total, "active": active}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)}


def _scrape_metrics(metrics_url: str) -> dict:
    try:
        with urllib.request.urlopen(metrics_url, timeout=2) as response:
            body = response.read().decode("utf-8", errors="replace")
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)}

    cache_hits = None
    cache_misses = None
    for line in body.splitlines():
        if line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        name, value = parts[0], parts[-1]
        # Strip prometheus labels: metric{label="x"} value
        base = name.split("{", 1)[0]
        try:
            numeric = float(value)
        except ValueError:
            continue
        if base == "cinematch_cache_hits_total":
            cache_hits = (cache_hits or 0.0) + numeric
        elif base == "cinematch_cache_misses_total":
            cache_misses = (cache_misses or 0.0) + numeric
    hit_rate = None
    if cache_hits is not None and cache_misses is not None:
        total = cache_hits + cache_misses
        if total > 0:
            hit_rate = round(cache_hits / total, 4)
    return {
        "ok": True,
        "cache_hits": cache_hits,
        "cache_misses": cache_misses,
        "cache_hit_rate": hit_rate,
    }


def sample_once(*, redis_url: str, database_url: str, metrics_url: str) -> dict:
    process = psutil.Process(os.getpid())
    return {
        "ts_utc": datetime.now(tz=UTC).isoformat(),
        "host_cpu_percent": psutil.cpu_percent(interval=0.2),
        "host_memory_percent": psutil.virtual_memory().percent,
        "collector_rss_mb": round(process.memory_info().rss / (1024 * 1024), 2),
        "redis": _redis_ping(redis_url),
        "postgres": _postgres_connections(database_url),
        "prometheus": _scrape_metrics(metrics_url),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--interval", type=float, default=5.0)
    parser.add_argument("--duration", type=float, default=120.0)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--redis-url", default=os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0"))
    parser.add_argument(
        "--database-url",
        default=os.getenv("DATABASE_URL", "postgres://127.0.0.1:5432/cinematch"),
    )
    parser.add_argument(
        "--metrics-url",
        default=os.getenv("LOADTEST_METRICS_URL", "http://127.0.0.1:8000/metrics/"),
    )
    args = parser.parse_args()

    samples: list[dict] = []
    args.output.parent.mkdir(parents=True, exist_ok=True)

    def _flush() -> None:
        payload = {
            "collected_at_utc": datetime.now(tz=UTC).isoformat(),
            "interval_seconds": args.interval,
            "duration_seconds": args.duration,
            "host": urlparse(args.metrics_url).hostname,
            "samples": samples,
        }
        args.output.write_text(json.dumps(payload, indent=2))

    def _on_signal(signum, _frame) -> None:  # noqa: ANN001
        _flush()
        raise SystemExit(0)

    import signal

    signal.signal(signal.SIGTERM, _on_signal)
    signal.signal(signal.SIGINT, _on_signal)

    deadline = time.time() + args.duration
    while time.time() < deadline:
        samples.append(
            sample_once(
                redis_url=args.redis_url,
                database_url=args.database_url,
                metrics_url=args.metrics_url,
            )
        )
        _flush()
        remaining = deadline - time.time()
        if remaining <= 0:
            break
        time.sleep(min(args.interval, remaining))

    _flush()
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
