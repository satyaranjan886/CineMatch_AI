# CineMatch AI

Personalized movie discovery platform with hybrid AI recommendations.

CineMatch combines collaborative filtering, content similarity, semantic search, and trending signals into a full-stack product — secure API, modern web UI, background ML jobs, and deployment-ready infrastructure.

---

## Overview

| Area | Details |
| --- | --- |
| Product | Personalized home feed, semantic search, catalog, watchlist, history |
| Backend | Django 5 + DRF, JWT auth, PostgreSQL/pgvector, Redis, Celery |
| Frontend | Next.js 15, React 19, TypeScript, Tailwind CSS |
| ML | ALS collaborative models, content ranking, embeddings, hybrid pipeline |
| Ops | Health/ready probes, Prometheus metrics, CI/CD, Locust load tests |
| Deploy | Docker Compose, Nginx, AWS Terraform sketches (multi-AZ design) |

---

## Features

**Users**
- Secure registration and login (JWT access + HttpOnly refresh cookie)
- Personalized home recommendations
- Movie catalog and detail pages
- Semantic search
- Watchlist, watch history, and continue watching
- Profile and preference controls

**Platform**
- Versioned collaborative-filtering model registry
- Async jobs for training, embeddings, and score refresh
- Staff analytics dashboard
- Structured logging and observability endpoints

---

## Quick start

**Requirements:** Python 3.12+, Node.js 20+, PostgreSQL 16 (pgvector), Redis 7+

```bash
cp .env.example .env
make setup
make dev
```

| Service | URL |
| --- | --- |
| Web app | http://localhost:3000 |
| API health | http://localhost:8000/api/v1/health/ |
| API reference | http://localhost:8000/api/docs/ |

```bash
make dev-backend     # API only
make dev-frontend    # UI only
```

### Docker

```bash
docker compose up --build
```

### Production Compose

```bash
cp .env.production.example .env.production
# set secrets locally — never commit them
docker compose -f docker-compose.prod.yml --env-file .env.production up --build -d
```

---

## Project structure

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

## Commands

| Command | Description |
| --- | --- |
| `make setup` | Install dependencies and run migrations |
| `make dev` | Start API and frontend |
| `make test` | Run backend tests |
| `make lint` | Lint backend and frontend |
| `make format` | Format backend code |
| `make migrate` | Apply database migrations |

---

## Engineering notes

- Secrets belong in environment files or a secret manager — not in git
- Local Compose Postgres is for development/staging; use managed Postgres for HA
- Terraform under `infrastructure/aws/` is illustrative and not auto-applied
- API is designed for horizontal scaling (stateless app tier, shared Redis/DB)

---

## License

Proprietary / all rights reserved unless otherwise specified by the repository owner.
