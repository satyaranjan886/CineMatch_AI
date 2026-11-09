# CineMatch AI

Open-source movie discovery platform with hybrid AI recommendations.

CineMatch combines collaborative filtering, content similarity, semantic search, and trending signals into a full-stack app: Django API, Next.js UI, Celery ML jobs, and Docker-ready infrastructure.

**License:** [MIT](LICENSE) — free to use, modify, and distribute.

---

## Stack

| Layer | Tech |
| --- | --- |
| Backend | Django 5, Django REST Framework, JWT auth |
| Frontend | Next.js 15, React 19, TypeScript, Tailwind CSS |
| Data | PostgreSQL 16 + pgvector, Redis 7 |
| ML | ALS collaborative models, content ranking, embeddings, hybrid ranking |
| Ops | Celery, Prometheus metrics, GitHub Actions, Locust load tests |
| Deploy | Docker Compose, Nginx, optional AWS Terraform sketches |

---

## Features

- Registration / login (JWT access + HttpOnly refresh cookie)
- Personalized home recommendations
- Movie catalog and detail pages
- Semantic search
- Watchlist, watch history, continue watching
- Profile and preference controls
- Versioned collaborative-filtering model registry
- Async jobs for training, embeddings, and score refresh
- Staff analytics dashboard

---

## Requirements

- Python 3.12+
- Node.js 20+
- PostgreSQL 16 with [pgvector](https://github.com/pgvector/pgvector) (or use Docker Compose)
- Redis 7+ (or use Docker Compose)
- `make` (optional but recommended)

---

## Quick start

### 1. Clone

```bash
git clone https://github.com/satyaranjan886/CineMatch_AI.git
cd CineMatch_AI
```

### 2. Environment

```bash
cp .env.example .env
```

Edit `.env` if needed. Local Docker defaults in `.env.example` work out of the box for Compose.

Generate a Django secret key:

```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

### 3a. Docker (easiest)

Starts Postgres, Redis, API, Celery, and related services:

```bash
docker compose up --build
```

In another terminal, install frontend deps and run the UI (or add the frontend service from Compose if you prefer all-in-Docker):

```bash
cd frontend && npm install && npm run dev
```

### 3b. Local (Makefile)

Requires Postgres + Redis running locally (or via Compose for just those services).

```bash
cp .env.example .env
make setup
make dev
```

| Service | URL |
| --- | --- |
| Web app | http://localhost:3000 |
| API health | http://localhost:8000/api/v1/health/ |
| API docs | http://localhost:8000/api/docs/ |

Useful commands:

```bash
make dev-backend    # API only
make dev-frontend   # UI only
make superuser      # create admin user
```

### 4. Seed sample movies

```bash
cd backend
../.venv/bin/python manage.py import_movies --sample
```

---

## Project layout

```text
backend/             Django API, domain apps, ML
frontend/            Next.js application
infrastructure/      Nginx + AWS Terraform sketches
loadtests/           Locust HTTP load testing
.github/workflows/   CI/CD pipelines
scripts/             Runtime and security helpers
requirements/        Python dependency sets
security/            Dependency exception policy
```

---

## Common commands

| Command | Description |
| --- | --- |
| `make setup` | Create venv, install deps, create DB, migrate |
| `make dev` | Start API + frontend |
| `make test` | Run backend tests |
| `make lint` | Lint backend and frontend |
| `make format` | Format backend code |
| `make migrate` | Apply database migrations |
| `make docker-up` | Start Docker Compose stack |
| `make docker-down` | Stop Docker Compose stack |

---

## Production (Compose)

```bash
cp .env.production.example .env.production
# set real secrets — never commit them
docker compose -f docker-compose.prod.yml --env-file .env.production up --build -d
```

Notes:

- Keep secrets in env files or a secret manager, not in git
- Local Compose Postgres is for development; prefer managed Postgres for HA
- Terraform under `infrastructure/aws/` is illustrative and not auto-applied
- Load tests: see [loadtests/README.md](loadtests/README.md) — use only against local/staging

---

## Contributing

Contributions are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md).

1. Fork the repository
2. Create a feature branch
3. Open a pull request against `main`

---

## License

This project is licensed under the [MIT License](LICENSE).
