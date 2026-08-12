"""Production settings. Secrets must come from the environment."""

import os
from pathlib import Path
from urllib.parse import urlparse

from django.core.exceptions import ImproperlyConfigured

from apps.common.security import cors_origins_are_https, csrf_origins_are_https

from .base import *  # noqa: F403
from .base import (
    CACHES,
    CELERY_BROKER_URL,
    CELERY_RESULT_BACKEND,
    CF_MODEL_ARTIFACT_DIR,
    DATABASES,
    LOGGING,
    REDIS_URL,
    env,
)

DEBUG = False

SECRET_KEY = os.environ.get("SECRET_KEY") or os.environ.get("DJANGO_SECRET_KEY")
if not SECRET_KEY:
    raise ImproperlyConfigured("Set the SECRET_KEY environment variable.")
if SECRET_KEY.startswith("dev-only-") or SECRET_KEY == "change-me-to-a-long-random-value":
    raise ImproperlyConfigured("Refusing to start production with a placeholder SECRET_KEY.")

ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=env.list("DJANGO_ALLOWED_HOSTS", default=[]))
if not ALLOWED_HOSTS:
    raise ImproperlyConfigured("Set the ALLOWED_HOSTS environment variable.")

CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])
if not CSRF_TRUSTED_ORIGINS:
    raise ImproperlyConfigured("Set CSRF_TRUSTED_ORIGINS (e.g. https://app.example.com).")
if not csrf_origins_are_https(CSRF_TRUSTED_ORIGINS):
    raise ImproperlyConfigured("CSRF_TRUSTED_ORIGINS must use https:// scheme in production.")

# Never allow wildcard CORS in production.
CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS", default=[])
if not CORS_ALLOWED_ORIGINS:
    raise ImproperlyConfigured(
        "Set CORS_ALLOWED_ORIGINS to explicit https frontend origins in production."
    )
if not cors_origins_are_https(CORS_ALLOWED_ORIGINS):
    raise ImproperlyConfigured("CORS_ALLOWED_ORIGINS must use https:// scheme in production.")
CORS_ALLOW_CREDENTIALS = True

# HTTPS defaults — keep local development on HTTP via development.py.
SECURE_SSL_REDIRECT = env.bool(
    "SECURE_SSL_REDIRECT", default=env.bool("DJANGO_SECURE_SSL_REDIRECT", default=True)
)
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
JWT_REFRESH_COOKIE_SECURE = True
JWT_REFRESH_COOKIE_SAMESITE = env("JWT_REFRESH_COOKIE_SAMESITE", default="Lax")

SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
X_FRAME_OPTIONS = "DENY"
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# HSTS only when HTTPS is enforced. Disable via SECURE_HSTS_SECONDS=0 behind broken TLS.
SECURE_HSTS_SECONDS = env.int(
    "SECURE_HSTS_SECONDS",
    default=31536000 if SECURE_SSL_REDIRECT else 0,
)
SECURE_HSTS_INCLUDE_SUBDOMAINS = env.bool(
    "SECURE_HSTS_INCLUDE_SUBDOMAINS",
    default=bool(SECURE_HSTS_SECONDS),
)
SECURE_HSTS_PRELOAD = env.bool(
    "SECURE_HSTS_PRELOAD",
    default=bool(SECURE_HSTS_SECONDS),
)

# Metrics scrape protection (Nginx allowlist + application-layer checks).
METRICS_ENABLED = env.bool("METRICS_ENABLED", default=True)
METRICS_SCRAPE_TOKEN = env("METRICS_SCRAPE_TOKEN", default="")
METRICS_ALLOW_PRIVATE_NETWORK = env.bool("METRICS_ALLOW_PRIVATE_NETWORK", default=True)
METRICS_REQUIRE_TOKEN = env.bool("METRICS_REQUIRE_TOKEN", default=False)
if METRICS_ENABLED and METRICS_REQUIRE_TOKEN and not METRICS_SCRAPE_TOKEN:
    raise ImproperlyConfigured(
        "METRICS_REQUIRE_TOKEN=true requires METRICS_SCRAPE_TOKEN in production."
    )

# Require TLS to Postgres unless explicitly overridden for private networks.
db_sslmode = env("DATABASE_SSLMODE", default="require")
DATABASES["default"].setdefault("OPTIONS", {})
DATABASES["default"]["OPTIONS"]["sslmode"] = db_sslmode

# CF artifacts must live on shared/object storage visible to every API + worker.
_cf_dir = Path(str(CF_MODEL_ARTIFACT_DIR))
if not _cf_dir.is_absolute():
    raise ImproperlyConfigured(
        "CF_MODEL_ARTIFACT_DIR must be an absolute path in production "
        "(e.g. /app/collaborative_models on a shared volume or synced object-storage cache)."
    )

# Cache soft-fail: Redis blips become misses; durable data stays in Postgres.
# Celery broker outages still block async work — scale workers separately.
CACHES["default"]["OPTIONS"]["IGNORE_EXCEPTIONS"] = env.bool(
    "CACHE_IGNORE_EXCEPTIONS", default=True
)

# Refuse unauthenticated Redis/Celery URLs in production.
for label, url in (
    ("REDIS_URL", REDIS_URL),
    ("CELERY_BROKER_URL", CELERY_BROKER_URL),
    ("CELERY_RESULT_BACKEND", CELERY_RESULT_BACKEND),
):
    parsed = urlparse(url)
    if parsed.scheme in {"redis", "rediss"} and not parsed.password:
        raise ImproperlyConfigured(
            f"{label} must include a password in production (redis://:password@host:6379/0)."
        )

LOGGING["handlers"]["console"]["formatter"] = "json"
LOGGING["root"]["level"] = "INFO"

SPECTACULAR_SETTINGS["SERVE_PERMISSIONS"] = ["rest_framework.permissions.IsAdminUser"]  # noqa: F405
