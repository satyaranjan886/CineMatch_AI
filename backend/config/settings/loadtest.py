"""Load-test settings: HTTP realism with throttles relaxed for sustained traffic.

Never use this module for public production. Point Locust only at staging/local.
"""

from .development import *  # noqa: F403

# Identify runs in logs / reports.
ENVIRONMENT_NAME = "loadtest"

# Locust will overwhelm default DRF throttles; keep auth/abuse limits but raise reads.
REST_FRAMEWORK = {
    **REST_FRAMEWORK,  # noqa: F405
    "DEFAULT_THROTTLE_RATES": {
        "anon": "10000/min",
        "user": "10000/min",
        "auth_register": "30/hour",
        "auth_login": "60/min",
        "auth_refresh": "120/min",
        "search": "5000/min",
        "interactions": "5000/min",
    },
}

# Optional stage timings in recommendation responses (X-Cinematch-Timing header).
LOADTEST_TIMING = True

# Prefer real sentence-transformers when installed; otherwise use deterministic mock.
try:
    import sentence_transformers  # noqa: F401
except ImportError:  # pragma: no cover
    EMBEDDING_PROVIDER_CLASS = "ml.embeddings.mock.MockEmbeddingProvider"
