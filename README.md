# CineMatch AI

**Personalized movie discovery powered by hybrid AI recommendations.**

CineMatch AI helps users find the next film worth watching — combining collaborative filtering, content similarity, semantic search, and trending signals into a production-ready web product.

Built as a full-stack system with a modern UI, secure APIs, background ML jobs, observability, automated tests, and deployment-ready Docker packaging.

---

## Why this project

| Client need | What CineMatch delivers |
| --- | --- |
| Personalized recommendations | Hybrid home feed (collaborative + content + semantic + popularity/trending) |
| Fast discovery | Semantic search over movie embeddings (pgvector) |
| Real product UX | Auth, catalog, watchlist, history, continue watching, preferences |
| Production engineering | JWT security, health checks, metrics, CI/CD, load-test harness |
| Scale path | Stateless API design + AWS multi-AZ Terraform sketches |

---

## Product features

### For end users
- **Sign up / sign in** with secure JWT access tokens and HttpOnly refresh cookies
- **Home recommendations** tailored to taste, with clear recommendation sections
- **Browse movies** by catalog, popularity, and genres
- **Semantic search** — find films by meaning, not only exact titles
- **Watchlist & history** to track what to watch and what you’ve seen
- **Continue watching** for in-progress titles
- **Profile & preferences** (languages, decades, favorite genres)

### For operators / admins
- Staff analytics dashboard for recommendation serve insights
- Health (`/health/`), readiness (`/ready/`), and Prometheus metrics
- Celery workers for training, embeddings, popularity/trending refresh
- Versioned collaborative-filtering model registry (exact model version in production)

---

## Tech stack

| Layer | Technology |
| --- | --- |
| Frontend | Next.js 15, React 19, TypeScript, Tailwind CSS |
| Backend API | Django 5, Django REST Framework, SimpleJWT |
| Database | PostgreSQL 16 + **pgvector** |
| Cache / queues | Redis |
| Async jobs | Celery (worker + beat) |
| ML | Collaborative filtering (ALS), content/TF-IDF, embeddings, hybrid ranking |
| Reverse proxy | Nginx (production Compose) |
| CI/CD | GitHub Actions (lint, tests, dependency security, Docker builds) |
| Cloud design | AWS Terraform sketches (ALB, RDS Multi-AZ, ElastiCache, S3, ECS notes) |

---

## Architecture (high level)

```text
Browser (Next.js)
      │
      ▼
API (Django / Gunicorn)  ──►  PostgreSQL + pgvector
      │                      ──►  Redis (cache + Celery broker)
      ▼
Celery workers / beat     ──►  ML training, embeddings, score refresh
```

The API layer is designed to be **stateless** (DB-backed sessions, shared Redis, versioned model artifacts) so it can grow from a single host to horizontal / multi-AZ deployment.

---

## Quick start

### Prerequisites
- Python 3.12+
- Node.js 20+
- PostgreSQL 16+ with [pgvector](https://github.com/pgvector/pgvector)
- Redis 7+
- Docker & Docker Compose (optional, recommended)

### Local development

```bash
cp .env.example .env
make setup
make dev
```

| Service | URL |
| --- | --- |
| Frontend | http://localhost:3000 |
| API health | http://localhost:8000/api/v1/health/ |
| API docs (Swagger) | http://localhost:8000/api/docs/ |

Or run separately:

```bash
make dev-backend    # terminal 1
make dev-frontend   # terminal 2
```

### Docker (full stack)

```bash
docker compose up --build
```

### Production-oriented single host

```bash
cp .env.production.example .env.production
# fill secrets offline — never commit real credentials
docker compose -f docker-compose.prod.yml --env-file .env.production up --build -d
```

---

## Quality & delivery signals

- **Backend + frontend automated tests** (pytest, Vitest)
- **Lint / typecheck / Django checks / migration checks** in CI
- **Dependency security gates** (`pip-audit` / `npm audit`) with tracked exceptions
- **HTTP load-test suite** (Locust) for realistic concurrent API traffic
- **Structured logging**, request IDs, readiness probes for load balancers

These are engineering practices clients expect for long-term product work — not demo-only scripts.

---

## Repository structure

```text
backend/            Django API, domain apps, ML pipelines
frontend/           Next.js product UI
infrastructure/     Nginx + AWS Terraform sketches
loadtests/          Locust scenarios, thresholds, runners
.github/workflows/  CI and CD pipelines
scripts/            Entrypoint, Gunicorn, security helpers
```

---

## Roadmap-ready next phases

Ideal follow-on engagements after launch:

1. **Single-node production cutover** — TLS, secrets, monitoring
2. **Managed data plane** — RDS PostgreSQL + ElastiCache Redis
3. **Horizontal API scale** — ALB + multiple app instances
4. **Multi-AZ HA** — apply/refine Terraform, S3 model artifacts, Celery autoscaling
5. **Model quality** — larger catalog, evaluation dashboards, A/B experiments

---

## Developer commands

| Command | Description |
| --- | --- |
| `make setup` | Install dependencies, create `.env`, migrate |
| `make dev` | Run API + frontend |
| `make test` | Backend test suite |
| `make lint` | Ruff + ESLint + TypeScript |
| `make format` | Format backend |
| `make migrate` | Apply database migrations |

---

## License / notes

- Do not commit `.env` or production secrets.
- Compose Postgres is for local/staging; managed Postgres is recommended for real HA.
- AWS Terraform under `infrastructure/aws/` is illustrative — apply only with operator review.

---

**CineMatch AI** — a complete recommendation product with the engineering foundation to ship, measure, and scale.
