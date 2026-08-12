"""Development settings — HTTP is allowed; never use in production."""

from .base import *  # noqa: F403
from .base import LOGGING, SECRET_KEY

DEBUG = True
ALLOWED_HOSTS = ["localhost", "127.0.0.1", "0.0.0.0", "testserver"]

if not SECRET_KEY:
    # Local-only fallback so `runserver` works without .env; never used in production.
    SECRET_KEY = "dev-only-insecure-secret-key-do-not-use-in-production"

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

CELERY_TASK_ALWAYS_EAGER = False
CELERY_TASK_EAGER_PROPAGATES = True

# Explicitly disable HTTPS enforcement for local HTTP development.
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
JWT_REFRESH_COOKIE_SECURE = False
SECURE_HSTS_SECONDS = 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD = False
CORS_ALLOW_ALL_ORIGINS = False

# Metrics are open on loopback in DEBUG; still fail closed if METRICS_REQUIRE_TOKEN is set.
METRICS_ALLOW_PRIVATE_NETWORK = True
METRICS_REQUIRE_TOKEN = False

SPECTACULAR_SETTINGS["SERVE_PERMISSIONS"] = ["rest_framework.permissions.AllowAny"]  # noqa: F405

LOGGING["handlers"]["console"]["formatter"] = "console"
LOGGING["root"]["level"] = "DEBUG"
