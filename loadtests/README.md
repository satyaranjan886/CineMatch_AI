# HTTP load testing (Locust)

This directory contains **realistic concurrent HTTP** load tests.

It is **not** the same as `scripts/perf_benchmark.py`, which uses Django
`APIClient` in-process (no network, often mock embeddings). Those numbers must
never be presented as production HTTP performance.

## Tooling

- **Locust** (preferred): Python, simple, fits this repo
- Config: `loadtests/config/thresholds.json`
- Users file: `loadtests/locustfile.py`

## Endpoints

| Request | Auth |
| --- | --- |
| `GET /api/v1/movies/` | optional |
| `GET /api/v1/movies/{id}/` | optional |
| `GET /api/v1/search/semantic/?q=` | optional (product search API) |
| `GET /api/v1/recommendations/home/` | required (emphasized) |

## Scenarios

Configured in `thresholds.json`:

| Name | Default users | Notes |
| --- | ---: | --- |
| low | 50 | smoke |
| normal | 100 | everyday concurrency |
| sustained | 250 | longer elevated load |
| burst | 500 | short spike |

These are **experiment knobs**, not claimed production capacity.

## Quick start (local/staging only)

```bash
# 1) Install tooling
.venv/bin/pip install -r requirements/loadtest.txt

# 2) Seed reproducible dataset
DJANGO_SETTINGS_MODULE=config.settings.loadtest \
  .venv/bin/python backend/manage.py seed_loadtest_data \
  --users 50 --movies 200 --with-embeddings

# 3) Start API with Gunicorn (not runserver for realism)
DJANGO_SETTINGS_MODULE=config.settings.loadtest \
  .venv/bin/gunicorn config.wsgi:application \
  --bind 127.0.0.1:8000 --workers 2 --threads 2 \
  --chdir backend

# 4) Run a scenario
chmod +x scripts/run_loadtest.sh
LOADTEST_HOST=http://127.0.0.1:8000 LOADTEST_LABEL=baseline \
  ./scripts/run_loadtest.sh low
```

Acceptance is evaluated from Locust CSV vs `thresholds.json`. A finished run with
high error rate / p95 is still a **failed** acceptance.

## Metrics

Locust captures: RPS, p50/p95/p99, errors/timeouts.

`collect_system_metrics.py` samples: CPU, memory, Redis ping latency, Postgres
connection counts, Celery list depth, Prometheus cache counters (when `/metrics`
is reachable).

When `LOADTEST_TIMING=true` (default in `config.settings.loadtest`), home
responses may include:

- `X-Cinematch-Cache: HIT|MISS`
- `X-Cinematch-Timing: candidate_generation_ms=…;ranking_ms=…;database_ms=…;…`

## Reports

Raw Locust CSV/HTML stays under `loadtests/results/` (gitignored).
