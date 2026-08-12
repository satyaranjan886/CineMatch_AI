"""Ensure the active CF model version is present in the local artifact cache."""

from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from apps.recommendations.models import CollaborativeModelArtifact
from ml.collaborative.artifacts import CollaborativeArtifactStore


class Command(BaseCommand):
    help = (
        "Download the active CollaborativeModelArtifact version into CF_MODEL_ARTIFACT_DIR. "
        "Requires CF_ARTIFACT_SYNC_ENABLED and an s3:// CF_ARTIFACT_URI_PREFIX when the "
        "files are not already local."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--version",
            default="",
            help="Specific version to sync (default: active registry row).",
        )

    def handle(self, *args, **options):
        version = (options.get("version") or "").strip()
        if version:
            artifact = CollaborativeModelArtifact.objects.filter(version=version).first()
            if artifact is None:
                raise CommandError(f"No CollaborativeModelArtifact for version {version!r}")
        else:
            artifact = (
                CollaborativeModelArtifact.objects.filter(is_active=True)
                .order_by("-trained_at")
                .first()
            )
            if artifact is None:
                raise CommandError("No active CollaborativeModelArtifact in the registry")
            version = artifact.version

        store = CollaborativeArtifactStore()
        store.ensure_local(version)
        if not store.has_version(version):
            raise CommandError(
                f"Version {version!r} is not present locally under {store.root}. "
                "Enable CF_ARTIFACT_SYNC_ENABLED with s3:// CF_ARTIFACT_URI_PREFIX, "
                "or copy artifacts onto a shared volume."
            )
        self.stdout.write(
            self.style.SUCCESS(
                f"CF artifact ready: model={artifact.model_name} version={version} "
                f"path={store.artifact_dir(version)} uri={artifact.artifact_path}"
            )
        )
