#!/bin/sh
set -eu

if [ -n "${PROMETHEUS_MULTIPROC_DIR:-}" ]; then
  # Scope by hostname so horizontally scaled API replicas never share multiproc files.
  # Gunicorn workers inside one container still share the scoped directory.
  if [ "${PROMETHEUS_MULTIPROC_SCOPED:-true}" = "true" ]; then
    PROMETHEUS_MULTIPROC_DIR="${PROMETHEUS_MULTIPROC_DIR%/}/$(hostname)"
    export PROMETHEUS_MULTIPROC_DIR
  fi
  mkdir -p "${PROMETHEUS_MULTIPROC_DIR}"
  # Fresh multiprocess registry per process start (Gunicorn master).
  find "${PROMETHEUS_MULTIPROC_DIR}" -type f -delete 2>/dev/null || true
fi

# When scaling API replicas, set RUN_MIGRATIONS=false / COLLECTSTATIC=false on all but
# one init/release job so migrate+collectstatic are not raced across instances.
if [ "${RUN_MIGRATIONS:-true}" = "true" ]; then
  python manage.py migrate --noinput
fi

if [ "${COLLECTSTATIC:-false}" = "true" ]; then
  python manage.py collectstatic --noinput
fi

exec "$@"
