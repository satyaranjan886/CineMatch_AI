# CineMatch AI

Movie discovery and personalized recommendation platform (Django/DRF + Next.js + Celery + Redis + Postgres/pgvector).

## Quick start

```bash
make setup
make dev
```

- API health: http://localhost:8000/api/v1/health/
- Frontend: http://localhost:3000

## Prerequisites

- Python 3.12+
- Node.js 20+
- PostgreSQL 16+ with [pgvector](https://github.com/pgvector/pgvector)
- Redis 7+
- Docker & Docker Compose (optional, recommended)

## Local development

```bash
cp .env.example .env
make setup
make dev-backend    # terminal 1
make dev-frontend   # terminal 2
# or: make dev
```

Never commit real credentials. Production template: `.env.production.example` → `.env.production` (gitignored).

## Capabilities

| Area | Highlights |
| --- | --- |
| Auth | JWT access + HttpOnly refresh cookie |
| Catalog | Movies, genres, similar titles |
| Interactions | History, watchlist, ratings, likes, continue watching |
| Recommendations | Popular, trending, collaborative, hybrid home + experiments |
| Search | Semantic search (pgvector embeddings) |
| Analytics | Serve events + staff dashboard |
| Ops | `/health`, `/ready`, `/metrics`, structured logs, Celery |
| Deploy | Multi-stage Docker images, Compose, GitHub Actions CI/CD |

## Docker

```bash
docker compose up --build
```

Production-oriented single host:

```bash
cp .env.production.example .env.production
# fill secrets offline
docker compose -f docker-compose.prod.yml --env-file .env.production up --build -d
```

## Developer commands

| Command | Description |
| --- | --- |
| `make setup` | Install deps, `.env`, DB, migrations |
| `make dev` | Run backend + frontend |
| `make test` | Backend pytest |
| `make lint` | Ruff + ESLint + TypeScript |
| `make format` | Format backend with Ruff |
| `make migrate` | Apply migrations |

## Project structure

```
backend/          Django API, domain apps, ml/
frontend/         Next.js + TypeScript + Tailwind
infrastructure/   Nginx, AWS Terraform sketches
loadtests/        Locust HTTP load tests
.github/          CI + CD workflows
```
