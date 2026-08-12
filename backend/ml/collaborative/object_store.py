"""Durable object-storage helpers for CF model artifacts (S3 → local cache).

Training and inference always pin an exact ``version`` from the Postgres registry.
Object storage holds the durable bytes; ``CF_MODEL_ARTIFACT_DIR`` is a local cache.
"""

from __future__ import annotations

import logging
from pathlib import Path
from urllib.parse import urlparse

from django.conf import settings

logger = logging.getLogger(__name__)


def parse_s3_uri(uri: str) -> tuple[str, str]:
    """Return (bucket, key_prefix) for ``s3://bucket/prefix``."""
    parsed = urlparse(uri)
    if parsed.scheme != "s3" or not parsed.netloc:
        raise ValueError(f"Expected s3:// URI, got {uri!r}")
    prefix = parsed.path.lstrip("/")
    return parsed.netloc, prefix.rstrip("/")


def artifact_uri_for_version(version: str) -> str | None:
    prefix = (getattr(settings, "CF_ARTIFACT_URI_PREFIX", "") or "").rstrip("/")
    if not prefix:
        return None
    return f"{prefix}/{version}"


def sync_enabled() -> bool:
    if not getattr(settings, "CF_ARTIFACT_SYNC_ENABLED", False):
        return False
    prefix = (getattr(settings, "CF_ARTIFACT_URI_PREFIX", "") or "").strip()
    return prefix.startswith("s3://")


def _boto3_client():
    try:
        import boto3
    except ImportError as exc:  # pragma: no cover - exercised when boto3 missing
        raise RuntimeError(
            "boto3 is required for CF_ARTIFACT_SYNC_ENABLED with an s3:// prefix. "
            "Install requirements/prod.txt (or pip install boto3)."
        ) from exc
    region = getattr(settings, "AWS_DEFAULT_REGION", None) or None
    return boto3.client("s3", region_name=region)


def upload_version_directory(*, version: str, local_dir: Path) -> str:
    """Upload ``model.pkl`` + ``metadata.json`` for a version; return s3 URI."""
    uri = artifact_uri_for_version(version)
    if not uri:
        raise ValueError("CF_ARTIFACT_URI_PREFIX is not configured")
    bucket, key_prefix = parse_s3_uri(uri)
    client = _boto3_client()
    uploaded = []
    for name in ("model.pkl", "metadata.json"):
        path = local_dir / name
        if not path.is_file():
            raise FileNotFoundError(f"Missing artifact file {path}")
        key = f"{key_prefix}/{name}" if key_prefix else name
        # When uri is s3://bucket/prefix/version, key_prefix already includes version.
        client.upload_file(str(path), bucket, key)
        uploaded.append(key)
    logger.info("Uploaded CF artifact version=%s keys=%s", version, uploaded)
    return uri


def download_version_directory(*, version: str, local_dir: Path) -> None:
    """Download durable bytes for ``version`` into the local cache directory."""
    uri = artifact_uri_for_version(version)
    if not uri:
        raise ValueError("CF_ARTIFACT_URI_PREFIX is not configured")
    bucket, key_prefix = parse_s3_uri(uri)
    client = _boto3_client()
    local_dir.mkdir(parents=True, exist_ok=True)
    for name in ("model.pkl", "metadata.json"):
        key = f"{key_prefix}/{name}" if key_prefix else name
        dest = local_dir / name
        client.download_file(bucket, key, str(dest))
    logger.info("Downloaded CF artifact version=%s into %s", version, local_dir)
