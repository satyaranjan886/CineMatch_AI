# syntax=docker/dockerfile:1
# Production backend image (API, Celery worker, Celery beat).
# Multi-stage: build wheels in builder, run as non-root in runtime.

FROM python:3.12-slim-bookworm AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /build

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements/base.txt requirements/prod.txt /build/requirements/
RUN pip install --upgrade pip \
    && pip wheel --wheel-dir /build/wheels -r /build/requirements/prod.txt


FROM python:3.12-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DJANGO_SETTINGS_MODULE=config.settings.production \
    PATH="/home/appuser/.local/bin:${PATH}"

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libpq5 \
        curl \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system --gid 10001 appuser \
    && useradd --system --uid 10001 --gid appuser --create-home --shell /usr/sbin/nologin appuser

COPY --from=builder /build/wheels /tmp/wheels
COPY requirements/base.txt requirements/prod.txt /tmp/requirements/
RUN pip install --upgrade pip \
    && pip install --no-index --find-links=/tmp/wheels -r /tmp/requirements/prod.txt \
    && rm -rf /tmp/wheels /tmp/requirements

COPY --chown=appuser:appuser backend /app
COPY --chown=appuser:appuser scripts/entrypoint.sh /entrypoint.sh
COPY --chown=appuser:appuser scripts/gunicorn.conf.py /gunicorn.conf.py
RUN chmod +x /entrypoint.sh \
    && mkdir -p /app/staticfiles \
    && chown -R appuser:appuser /app/staticfiles

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD curl -fsS "http://127.0.0.1:8000/health/" || exit 1

ENTRYPOINT ["/entrypoint.sh"]
CMD ["gunicorn", "config.wsgi:application", "--config", "/gunicorn.conf.py"]
