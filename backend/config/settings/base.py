"""Shared Django settings for CineMatch AI."""

from datetime import timedelta
from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent.parent
REPO_ROOT = BASE_DIR.parent

env = environ.Env(
    DEBUG=(bool, False),
    ALLOWED_HOSTS=(list, ["localhost", "127.0.0.1"]),
    SECURE_SSL_REDIRECT=(bool, False),
    DB_CONN_MAX_AGE=(int, 60),
    JWT_ACCESS_TOKEN_LIFETIME_MINUTES=(int, 15),
    JWT_REFRESH_TOKEN_LIFETIME_DAYS=(int, 7),
    REC_WEIGHT_COLLABORATIVE=(float, 0.30),
    REC_WEIGHT_CONTENT=(float, 0.25),
    REC_WEIGHT_GENRE_PREFERENCE=(float, 0.15),
    REC_WEIGHT_POPULARITY=(float, 0.10),
    REC_WEIGHT_TRENDING=(float, 0.10),
    REC_WEIGHT_FRESHNESS=(float, 0.05),
    REC_WEIGHT_AFFINITY=(float, 0.05),
    RECOMMENDATION_POPULAR_CACHE_TTL=(int, 900),
    RECOMMENDATION_TRENDING_CACHE_TTL=(int, 300),
    RECOMMENDATION_MIN_VOTES_PRIOR=(float, 10.0),
    RECOMMENDATION_TRENDING_DEFAULT_WINDOW_HOURS=(int, 24),
    RECOMMENDATION_TRENDING_HALF_LIFE_HOURS=(float, 24.0),
    CONTENT_SIMILARITY_MAX_FEATURES=(int, 5000),
    CONTENT_PROFILE_LIKE_WEIGHT=(float, 3.0),
    CONTENT_PROFILE_RATING_WEIGHT=(float, 2.5),
    CONTENT_PROFILE_COMPLETE_WEIGHT=(float, 2.0),
    CONTENT_PROFILE_HISTORY_WEIGHT=(float, 1.0),
    CONTENT_PROFILE_MIN_RATING=(float, 7.0),
    CF_MIN_USER_INTERACTIONS=(int, 3),
    CF_ALS_FACTORS=(int, 64),
    CF_ALS_ITERATIONS=(int, 15),
    CF_ALS_REGULARIZATION=(float, 0.01),
    CF_ALS_RANDOM_STATE=(int, 42),
    CF_EVAL_AT_K=(int, 10),
    RECOMMENDATION_COLLABORATIVE_CACHE_TTL=(int, 600),
    RECOMMENDATION_VERSION=(str, "v1"),
    HYBRID_HOME_CACHE_TTL=(int, 600),
    HYBRID_DIVERSITY_LAMBDA=(float, 0.72),
    MOVIE_DETAIL_CACHE_TTL=(int, 600),
    SEMANTIC_SEARCH_CACHE_TTL=(int, 120),
    HOME_PRECOMPUTE_LOOKBACK_HOURS=(int, 24),
    HOME_PRECOMPUTE_USER_LIMIT=(int, 200),
    EVAL_K_VALUES=(list, [5, 10, 20]),
    EVAL_MIN_USERS=(int, 5),
    EVAL_MIN_TEST_INTERACTIONS=(int, 10),
    EVAL_MIN_INTERACTIONS=(int, 2),
    EVAL_RANDOM_SEED=(int, 42),
    EVAL_USE_CATALOG_PRIOR=(bool, False),
    EMBEDDING_MODEL_NAME=(str, "sentence-transformers/all-MiniLM-L6-v2"),
    EMBEDDING_MODEL_VERSION=(str, "v1"),
    EMBEDDING_DIMENSIONS=(int, 384),
    EMBEDDING_BATCH_SIZE=(int, 32),
)

environ.Env.read_env(REPO_ROOT / ".env", overwrite=False)

# Never ship with a hardcoded production secret. Development may set a local default.
SECRET_KEY = env("SECRET_KEY", default=env("DJANGO_SECRET_KEY", default=None))
DEBUG = env("DEBUG", default=env("DJANGO_DEBUG", default=False))
ALLOWED_HOSTS = env.list(
    "ALLOWED_HOSTS", default=env.list("DJANGO_ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])
)

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.postgres",
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",
    "drf_spectacular",
    "apps.common",
    "apps.accounts",
    "apps.movies",
    "apps.interactions",
    "apps.recommendations",
    "apps.search",
    "apps.analytics",
    "apps.experiments",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "apps.common.middleware.RequestIDMiddleware",
    "apps.common.middleware.RequestObservabilityMiddleware",
    "apps.common.middleware.SecurityHeadersMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

DATABASES = {
    "default": env.db(
        "DATABASE_URL",
        default="postgres://127.0.0.1:5432/cinematch",
    )
}
DATABASES["default"]["CONN_MAX_AGE"] = env("DB_CONN_MAX_AGE")
DATABASES["default"]["ATOMIC_REQUESTS"] = False
DATABASES["default"]["OPTIONS"] = {"connect_timeout": 5}

AUTH_USER_MODEL = "accounts.User"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 8},
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

# Database-backed sessions — required for multi-instance API (no local filesystem sessions).
SESSION_ENGINE = "django.contrib.sessions.backends.db"

REDIS_URL = env("REDIS_URL", default="redis://127.0.0.1:6379/0")

CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": REDIS_URL,
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            # When True, Redis errors become cache misses instead of 500s.
            # Durable state still lives in Postgres; Celery broker is separate.
            "IGNORE_EXCEPTIONS": env.bool("CACHE_IGNORE_EXCEPTIONS", default=False),
        },
        "KEY_PREFIX": "cinematch",
        "TIMEOUT": 300,
    }
}

CELERY_BROKER_URL = env("CELERY_BROKER_URL", default="redis://127.0.0.1:6379/1")
CELERY_RESULT_BACKEND = env("CELERY_RESULT_BACKEND", default="redis://127.0.0.1:6379/2")
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_ACKS_LATE = True
CELERY_TASK_REJECT_ON_WORKER_LOST = True
RECOMMENDATION_POPULAR_CACHE_TTL = env("RECOMMENDATION_POPULAR_CACHE_TTL")
RECOMMENDATION_TRENDING_CACHE_TTL = env("RECOMMENDATION_TRENDING_CACHE_TTL")
RECOMMENDATION_MIN_VOTES_PRIOR = env("RECOMMENDATION_MIN_VOTES_PRIOR")
RECOMMENDATION_TRENDING_DEFAULT_WINDOW_HOURS = env("RECOMMENDATION_TRENDING_DEFAULT_WINDOW_HOURS")
RECOMMENDATION_TRENDING_HALF_LIFE_HOURS = env("RECOMMENDATION_TRENDING_HALF_LIFE_HOURS")
RECOMMENDATION_TRENDING_WINDOWS_HOURS = env.list(
    "RECOMMENDATION_TRENDING_WINDOWS_HOURS",
    default=["24", "168"],
)
RECOMMENDATION_TRENDING_WINDOWS_HOURS = [
    int(value) for value in RECOMMENDATION_TRENDING_WINDOWS_HOURS
]

CONTENT_SIMILARITY_MAX_FEATURES = env("CONTENT_SIMILARITY_MAX_FEATURES")
CONTENT_PROFILE_LIKE_WEIGHT = env("CONTENT_PROFILE_LIKE_WEIGHT")
CONTENT_PROFILE_RATING_WEIGHT = env("CONTENT_PROFILE_RATING_WEIGHT")
CONTENT_PROFILE_COMPLETE_WEIGHT = env("CONTENT_PROFILE_COMPLETE_WEIGHT")
CONTENT_PROFILE_HISTORY_WEIGHT = env("CONTENT_PROFILE_HISTORY_WEIGHT")
CONTENT_PROFILE_MIN_RATING = env("CONTENT_PROFILE_MIN_RATING")

CF_INTERACTION_WEIGHTS = {
    "watch_complete": env.float("CF_WEIGHT_WATCH_COMPLETE", default=5.0),
    "like": env.float("CF_WEIGHT_LIKE", default=4.0),
    "rating": env.float("CF_WEIGHT_RATING", default=3.0),
    "watch_progress": env.float("CF_WEIGHT_WATCH_PROGRESS", default=2.0),
    "watchlist_add": env.float("CF_WEIGHT_WATCHLIST_ADD", default=1.5),
}
CF_MIN_USER_INTERACTIONS = env("CF_MIN_USER_INTERACTIONS")
CF_ALS_FACTORS = env("CF_ALS_FACTORS")
CF_ALS_ITERATIONS = env("CF_ALS_ITERATIONS")
CF_ALS_REGULARIZATION = env("CF_ALS_REGULARIZATION")
CF_ALS_RANDOM_STATE = env("CF_ALS_RANDOM_STATE")
CF_EVAL_AT_K = env("CF_EVAL_AT_K")
CF_MODEL_ARTIFACT_DIR = env("CF_MODEL_ARTIFACT_DIR", default="collaborative_models")
# Durable URI prefix for registry metadata (e.g. s3://cinematch-models/cf).
# With CF_ARTIFACT_SYNC_ENABLED=true, train uploads and inference downloads into
# CF_MODEL_ARTIFACT_DIR (local cache). Postgres CollaborativeModelArtifact.version is authoritative.
CF_ARTIFACT_URI_PREFIX = env("CF_ARTIFACT_URI_PREFIX", default="")
CF_ARTIFACT_SYNC_ENABLED = env.bool("CF_ARTIFACT_SYNC_ENABLED", default=False)
CF_MODEL_NAME = env("CF_MODEL_NAME", default="collaborative_als")
AWS_DEFAULT_REGION = env("AWS_DEFAULT_REGION", default="")
# Optional media bucket (configure django-storages separately). Empty = local MEDIA_ROOT.
AWS_STORAGE_BUCKET_NAME = env("AWS_STORAGE_BUCKET_NAME", default="")
CF_TRAIN_LOCK_TIMEOUT_SECONDS = env.int("CF_TRAIN_LOCK_TIMEOUT_SECONDS", default=3600)
EMBEDDING_JOB_LOCK_TIMEOUT_SECONDS = env.int("EMBEDDING_JOB_LOCK_TIMEOUT_SECONDS", default=3600)
RECOMMENDATION_COLLABORATIVE_CACHE_TTL = env("RECOMMENDATION_COLLABORATIVE_CACHE_TTL")
RECOMMENDATION_VERSION = env("RECOMMENDATION_VERSION")
HYBRID_HOME_CACHE_TTL = env("HYBRID_HOME_CACHE_TTL")
HYBRID_DIVERSITY_LAMBDA = env("HYBRID_DIVERSITY_LAMBDA")
MOVIE_DETAIL_CACHE_TTL = env("MOVIE_DETAIL_CACHE_TTL")
SEMANTIC_SEARCH_CACHE_TTL = env("SEMANTIC_SEARCH_CACHE_TTL")
HOME_PRECOMPUTE_LOOKBACK_HOURS = env("HOME_PRECOMPUTE_LOOKBACK_HOURS")
HOME_PRECOMPUTE_USER_LIMIT = env("HOME_PRECOMPUTE_USER_LIMIT")
HYBRID_CANDIDATE_LIMITS = {
    "collaborative": 100,
    "content": 100,
    "semantic": 100,
    "trending": 50,
    "popular": 50,
    "genre_preference": 50,
    "recently_watched": 50,
}
EVAL_K_VALUES = [int(value) for value in env.list("EVAL_K_VALUES", default=[5, 10, 20])]
EVAL_MIN_USERS = env("EVAL_MIN_USERS")
EVAL_MIN_TEST_INTERACTIONS = env("EVAL_MIN_TEST_INTERACTIONS")
EVAL_MIN_INTERACTIONS = env("EVAL_MIN_INTERACTIONS")
EVAL_RANDOM_SEED = env("EVAL_RANDOM_SEED")
EVAL_USE_CATALOG_PRIOR = env.bool("EVAL_USE_CATALOG_PRIOR", default=False)

EMBEDDING_PROVIDER_CLASS = env(
    "EMBEDDING_PROVIDER_CLASS",
    default="ml.embeddings.sentence_transformer.SentenceTransformerEmbeddingProvider",
)
EMBEDDING_MODEL_NAME = env("EMBEDDING_MODEL_NAME")
EMBEDDING_MODEL_VERSION = env("EMBEDDING_MODEL_VERSION")
EMBEDDING_DIMENSIONS = env("EMBEDDING_DIMENSIONS")
EMBEDDING_BATCH_SIZE = env("EMBEDDING_BATCH_SIZE")

CELERY_BEAT_SCHEDULE = {
    "recommendations-update-popularity-scores": {
        "task": "recommendations.update_popularity_scores",
        "schedule": 900.0,
    },
    "recommendations-update-trending-scores": {
        "task": "recommendations.update_trending_scores",
        "schedule": 300.0,
    },
    "recommendations-generate-home-recommendations": {
        "task": "recommendations.generate_home_recommendations",
        "schedule": 1800.0,
    },
    "recommendations-train-collaborative-model": {
        "task": "recommendations.train_collaborative_model",
        "schedule": 86400.0,
    },
    "search-generate-movie-embeddings": {
        "task": "search.generate_movie_embeddings",
        "schedule": 21600.0,
    },
    "analytics-compute-daily-snapshot": {
        "task": "analytics.compute_daily_snapshot",
        "schedule": 3600.0,
    },
}

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "DEFAULT_PAGINATION_CLASS": "apps.common.pagination.StandardPageNumberPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_THROTTLE_CLASSES": (
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ),
    "DEFAULT_THROTTLE_RATES": {
        "anon": "60/min",
        "user": "120/min",
        "auth_register": "10/hour",
        "auth_login": "20/min",
        "auth_refresh": "30/min",
        "profile_update": "60/min",
        "search": "30/min",
        "interactions": "120/min",
    },
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_VERSIONING_CLASS": "rest_framework.versioning.URLPathVersioning",
    "ALLOWED_VERSIONS": ("v1",),
    "DEFAULT_VERSION": "v1",
    "EXCEPTION_HANDLER": "apps.common.exceptions.api_exception_handler",
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=env("JWT_ACCESS_TOKEN_LIFETIME_MINUTES")),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=env("JWT_REFRESH_TOKEN_LIFETIME_DAYS")),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
    "ALGORITHM": "HS256",
    "AUTH_HEADER_TYPES": ("Bearer",),
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
    "AUTH_TOKEN_CLASSES": ("rest_framework_simplejwt.tokens.AccessToken",),
}

# Refresh token is also stored in an HttpOnly cookie (see apps.accounts.cookies).
JWT_REFRESH_COOKIE_NAME = "cinematch_refresh"
JWT_REFRESH_COOKIE_PATH = "/"
JWT_REFRESH_COOKIE_SAMESITE = env("JWT_REFRESH_COOKIE_SAMESITE", default="Lax")
JWT_REFRESH_COOKIE_SECURE = env.bool("JWT_REFRESH_COOKIE_SECURE", default=False)

SPECTACULAR_SETTINGS = {
    "TITLE": "CineMatch AI API",
    "DESCRIPTION": "Movie discovery and personalized recommendation platform.",
    "VERSION": "0.1.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "SERVE_PERMISSIONS": ["rest_framework.permissions.IsAdminUser"],
}

CORS_ALLOWED_ORIGINS = env.list(
    "CORS_ALLOWED_ORIGINS",
    default=["http://localhost:3000", "http://127.0.0.1:3000"],
)
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_ALL_ORIGINS = False

SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=False)
SECURE_HSTS_SECONDS = env.int("SECURE_HSTS_SECONDS", default=0)
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD = False
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
CONTENT_SECURITY_POLICY = (
    "default-src 'self'; "
    "base-uri 'self'; "
    "frame-ancestors 'none'; "
    "form-action 'self'; "
    "object-src 'none'"
)
PERMISSIONS_POLICY = "camera=(), microphone=(), geolocation=()"
INTERACTION_METADATA_MAX_BYTES = env.int("INTERACTION_METADATA_MAX_BYTES", default=4096)

# Metrics defaults (production tightens further).
METRICS_ENABLED = env.bool("METRICS_ENABLED", default=True)
METRICS_SCRAPE_TOKEN = env("METRICS_SCRAPE_TOKEN", default="")
METRICS_ALLOW_PRIVATE_NETWORK = env.bool("METRICS_ALLOW_PRIVATE_NETWORK", default=True)
METRICS_REQUIRE_TOKEN = env.bool("METRICS_REQUIRE_TOKEN", default=False)

# Ranking weights (hybrid home).
RECOMMENDATION_WEIGHTS = {
    "collaborative": env("REC_WEIGHT_COLLABORATIVE"),
    "content": env("REC_WEIGHT_CONTENT"),
    "genre_preference": env("REC_WEIGHT_GENRE_PREFERENCE"),
    "popularity": env("REC_WEIGHT_POPULARITY"),
    "trending": env("REC_WEIGHT_TRENDING"),
    "freshness": env("REC_WEIGHT_FRESHNESS"),
    "affinity": env("REC_WEIGHT_AFFINITY"),
}

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "request_id": {
            "()": "apps.common.logging.RequestContextFilter",
        }
    },
    "formatters": {
        "json": {
            "()": "apps.common.logging.JsonFormatter",
        },
        "console": {
            "format": (
                "[{asctime}] {levelname} {name} request_id={request_id} "
                "user_id={user_id} endpoint={endpoint} {message}"
            ),
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "filters": ["request_id"],
            "formatter": "console",
        }
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
    "loggers": {
        "django.request": {"level": "WARNING", "propagate": True},
        "celery": {"level": "INFO", "propagate": True},
        "cinematch.request": {"level": "INFO", "propagate": True},
        "cinematch.observability": {"level": "INFO", "propagate": True},
    },
}

# Observability
REDIS_HEALTH_REQUIRED = env.bool("REDIS_HEALTH_REQUIRED", default=True)
