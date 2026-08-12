"""Test settings. Uses real Postgres; Redis when USE_REDIS_CACHE=1 (CI)."""

import os

from .base import *  # noqa: F403
from .base import DATABASES, REDIS_URL

DEBUG = True
SECRET_KEY = "test-secret-key-not-for-production"
ALLOWED_HOSTS = ["localhost", "127.0.0.1", "testserver"]

DATABASES["default"]["CONN_MAX_AGE"] = 0

if os.environ.get("USE_REDIS_CACHE", "").lower() in {"1", "true", "yes"}:
    CACHES = {
        "default": {
            "BACKEND": "django_redis.cache.RedisCache",
            "LOCATION": os.environ.get("REDIS_URL", REDIS_URL),
            "OPTIONS": {
                "CLIENT_CLASS": "django_redis.client.DefaultClient",
                "IGNORE_EXCEPTIONS": os.environ.get("CACHE_IGNORE_EXCEPTIONS", "false").lower()
                in {"1", "true", "yes"},
            },
            "KEY_PREFIX": "cinematch-test",
            "TIMEOUT": 300,
        }
    }
else:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "cinematch-test",
        }
    }

CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
CELERY_BROKER_URL = "memory://"
CELERY_RESULT_BACKEND = "cache+memory://"

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"] = {  # noqa: F405
    "anon": "1000/min",
    "user": "1000/min",
    "auth_register": "1000/hour",
    "auth_login": "1000/min",
    "auth_refresh": "1000/min",
    "profile_update": "1000/min",
    "search": "1000/min",
    "interactions": "1000/min",
}

EMBEDDING_PROVIDER_CLASS = "ml.embeddings.mock.MockEmbeddingProvider"
EMBEDDING_MODEL_NAME = "mock-embedder"
EMBEDDING_DIMENSIONS = 384

JWT_REFRESH_COOKIE_SECURE = False
SECURE_SSL_REDIRECT = False
SECURE_HSTS_SECONDS = 0
CORS_ALLOW_ALL_ORIGINS = False
SPECTACULAR_SETTINGS["SERVE_PERMISSIONS"] = ["rest_framework.permissions.AllowAny"]  # noqa: F405
REDIS_HEALTH_REQUIRED = os.environ.get("USE_REDIS_CACHE", "").lower() in {"1", "true", "yes"}
METRICS_ENABLED = True
METRICS_SCRAPE_TOKEN = ""
METRICS_ALLOW_PRIVATE_NETWORK = True
METRICS_REQUIRE_TOKEN = False
