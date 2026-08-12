"""Tests for S3 ↔ local CF artifact sync (mocked; no live AWS)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from django.test import override_settings

from ml.collaborative.artifacts import CollaborativeArtifactStore
from ml.collaborative.object_store import parse_s3_uri


def test_parse_s3_uri():
    bucket, prefix = parse_s3_uri("s3://cinematch-models/cf/cf-v1")
    assert bucket == "cinematch-models"
    assert prefix == "cf/cf-v1"


@override_settings(
    MEDIA_ROOT="/tmp/cinematch-cf-test-media",
    CF_MODEL_ARTIFACT_DIR="collaborative_models",
    CF_ARTIFACT_URI_PREFIX="s3://cinematch-models/cf",
    CF_ARTIFACT_SYNC_ENABLED=True,
)
def test_ensure_local_downloads_when_missing(tmp_path, settings):
    settings.MEDIA_ROOT = tmp_path
    settings.CF_MODEL_ARTIFACT_DIR = "collaborative_models"
    store = CollaborativeArtifactStore()
    version = "cf-test-download"

    def fake_download(*, version: str, local_dir: Path):
        local_dir.mkdir(parents=True, exist_ok=True)
        (local_dir / "model.pkl").write_bytes(b"pkl")
        (local_dir / "metadata.json").write_text(
            json.dumps(
                {
                    "version": version,
                    "algorithm": "als",
                    "user_count": 0,
                    "item_count": 0,
                    "interaction_count": 0,
                    "hyperparameters": {},
                    "metrics": {},
                    "trained_at": "2026-01-01T00:00:00+00:00",
                    "user_ids": [],
                    "item_ids": [],
                }
            )
        )

    with patch(
        "ml.collaborative.object_store.download_version_directory",
        side_effect=fake_download,
    ) as mocked:
        store.ensure_local(version)
        mocked.assert_called_once()
    assert store.has_version(version)


@override_settings(CF_ARTIFACT_SYNC_ENABLED=True, CF_ARTIFACT_URI_PREFIX="s3://bucket/cf")
def test_upload_version_directory_uses_exact_keys(tmp_path, settings):
    from ml.collaborative import object_store

    version = "cf-abc"
    local_dir = tmp_path / version
    local_dir.mkdir()
    (local_dir / "model.pkl").write_bytes(b"x")
    (local_dir / "metadata.json").write_text("{}")

    client = MagicMock()
    with patch.object(object_store, "_boto3_client", return_value=client):
        uri = object_store.upload_version_directory(version=version, local_dir=local_dir)

    assert uri == "s3://bucket/cf/cf-abc"
    keys = {call.args[2] for call in client.upload_file.call_args_list}
    assert keys == {"cf/cf-abc/model.pkl", "cf/cf-abc/metadata.json"}


@override_settings(
    CF_ARTIFACT_SYNC_ENABLED=True,
    CF_ARTIFACT_URI_PREFIX="s3://bucket/cf",
)
def test_sync_enabled_true_for_s3_prefix():
    from ml.collaborative.object_store import sync_enabled

    assert sync_enabled() is True


@override_settings(
    CF_ARTIFACT_SYNC_ENABLED=True,
    CF_ARTIFACT_URI_PREFIX="/shared/cf",
)
def test_sync_enabled_false_for_non_s3_prefix():
    from ml.collaborative.object_store import sync_enabled

    assert sync_enabled() is False
