.PHONY: help setup dev dev-backend dev-frontend install frontend-install migrate makemigrations test lint format shell logs docker-up docker-down superuser

PYTHON ?= python3.12
BACKEND := backend
FRONTEND := frontend
VENV_PY := "$(CURDIR)/.venv/bin/python"
VENV_BIN := "$(CURDIR)/.venv/bin"
export DJANGO_SETTINGS_MODULE ?= config.settings.development

help:
	@echo "CineMatch AI — developer commands"
	@echo "  make setup            Install deps, create .env, DB, run migrations"
	@echo "  make dev              Run backend + frontend (blocking)"
	@echo "  make dev-backend      Run Django API only"
	@echo "  make dev-frontend     Run Next.js dev server only"
	@echo "  make test             Run backend pytest suite"
	@echo "  make lint             Lint backend + frontend"
	@echo "  make format           Format backend (Ruff) + frontend (Prettier via Next if configured)"
	@echo "  make migrate          Apply Django migrations"
	@echo "  make makemigrations   Create Django migrations"
	@echo "  make shell            Django shell"
	@echo "  make logs             Tail Docker Compose logs"
	@echo "  make docker-up        Start Docker Compose stack"
	@echo "  make docker-down      Stop Docker Compose stack"

.venv/bin/python:
	$(PYTHON) -m venv .venv
	.venv/bin/pip install --upgrade pip

install: .venv/bin/python
	.venv/bin/pip install -r requirements/dev.txt

frontend-install:
	cd $(FRONTEND) && npm install

env:
	@test -f .env || cp .env.example .env

db-create:
	createdb cinematch || true

setup: env install frontend-install db-create migrate

migrate:
	cd $(BACKEND) && $(VENV_PY) manage.py migrate

makemigrations:
	cd $(BACKEND) && $(VENV_PY) manage.py makemigrations

dev-backend:
	cd $(BACKEND) && $(VENV_PY) manage.py runserver 0.0.0.0:8000

dev-frontend:
	cd $(FRONTEND) && npm run dev

dev:
	@trap 'kill 0' INT TERM; \
	(cd $(BACKEND) && $(VENV_PY) manage.py runserver 0.0.0.0:8000) & \
	(cd $(FRONTEND) && npm run dev) & \
	wait

test:
	$(VENV_BIN)/pytest

lint:
	$(VENV_BIN)/ruff check backend
	$(VENV_BIN)/ruff format --check backend
	cd $(FRONTEND) && npm run lint
	cd $(FRONTEND) && npm run typecheck

format:
	$(VENV_BIN)/ruff check --fix backend
	$(VENV_BIN)/ruff format backend

shell:
	cd $(BACKEND) && $(VENV_PY) manage.py shell

logs:
	docker compose logs -f backend celery_worker celery_beat postgres redis

docker-up:
	docker compose up --build

docker-down:
	docker compose down

superuser:
	cd $(BACKEND) && $(VENV_PY) manage.py createsuperuser
