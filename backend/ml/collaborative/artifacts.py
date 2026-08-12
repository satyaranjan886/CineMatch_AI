"""Versioned collaborative filtering artifact storage."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

from django.conf import settings

from ml.collaborative.dataset import InteractionDataset
from ml.collaborative.model import CollaborativeFilteringModel

# Stable algorithm identity for registry / observability.
CF_MODEL_NAME = "collaborative_als"


@dataclass(frozen=True)
class ArtifactMetadata:
    version: str
    algorithm: str
    user_count: int
    item_count: int
    interaction_count: int
    hyperparameters: dict
    metrics: dict
    trained_at: str
    user_ids: list[str]
    item_ids: list[str]
    model_name: str = CF_MODEL_NAME
    dataset_version: str = ""
    artifact_location: str = ""

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class ModelArtifactDescriptor:
    """Durable identity for a trained recommendation model (not "whatever file exists")."""

    model_name: str
    model_version: str
    artifact_location: str
    created_at: str
    dataset_version: str
    metrics: dict
    is_active: bool = False

    def as_dict(self) -> dict:
        return asdict(self)


class CollaborativeArtifactStore:
    """Persist and load versioned CF model artifacts on durable shared storage."""

    MODEL_FILENAME = "model.pkl"
    METADATA_FILENAME = "metadata.json"

    def __init__(self, *, root: Path | None = None):
        configured = Path(getattr(settings, "CF_MODEL_ARTIFACT_DIR", "collaborative_models"))
        if root is not None:
            self.root = root
        elif configured.is_absolute():
            self.root = configured
        else:
            media_root = Path(getattr(settings, "MEDIA_ROOT", settings.BASE_DIR / "media"))
            self.root = media_root / configured
        self.root.mkdir(parents=True, exist_ok=True)

    def create_version(self) -> str:
        timestamp = datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%S%fZ")
        return f"cf-{timestamp}-{uuid4().hex[:8]}"

    def artifact_dir(self, version: str) -> Path:
        return self.root / version

    def model_path(self, version: str) -> Path:
        return self.artifact_dir(version) / self.MODEL_FILENAME

    def metadata_path(self, version: str) -> Path:
        return self.artifact_dir(version) / self.METADATA_FILENAME

    def dataset_version_for(self, dataset: InteractionDataset) -> str:
        return (
            f"interactions-n{dataset.interaction_count}-u{dataset.user_count}-i{dataset.item_count}"
        )

    def save(
        self,
        *,
        version: str,
        model: CollaborativeFilteringModel,
        dataset: InteractionDataset,
        metrics: dict | object,
        hyperparameters: dict,
        model_name: str = CF_MODEL_NAME,
    ) -> ArtifactMetadata:
        artifact_dir = self.artifact_dir(version)
        artifact_dir.mkdir(parents=True, exist_ok=True)

        model_path = artifact_dir / self.MODEL_FILENAME
        model.save(model_path)

        artifact_location = str(artifact_dir.resolve())
        uri_prefix = (getattr(settings, "CF_ARTIFACT_URI_PREFIX", "") or "").rstrip("/")
        if uri_prefix:
            artifact_location = f"{uri_prefix}/{version}"

        if hasattr(metrics, "as_dict"):
            metrics_payload = metrics.as_dict()  # type: ignore[union-attr]
        else:
            metrics_payload = dict(metrics)

        metadata = ArtifactMetadata(
            version=version,
            algorithm=hyperparameters.get("algorithm", "als"),
            model_name=model_name,
            dataset_version=self.dataset_version_for(dataset),
            artifact_location=artifact_location,
            user_count=dataset.user_count,
            item_count=dataset.item_count,
            interaction_count=dataset.interaction_count,
            hyperparameters=hyperparameters,
            metrics=metrics_payload,
            trained_at=datetime.now(tz=UTC).isoformat(),
            user_ids=[str(user_id) for user_id in dataset.user_ids],
            item_ids=[str(item_id) for item_id in dataset.item_ids],
        )
        self.metadata_path(version).write_text(
            json.dumps(metadata.as_dict(), indent=2, sort_keys=True)
        )
        if self._should_sync_remote():
            from ml.collaborative.object_store import upload_version_directory

            remote_uri = upload_version_directory(version=version, local_dir=artifact_dir)
            # Prefer durable URI in returned metadata / registry.
            metadata = ArtifactMetadata(**{**metadata.as_dict(), "artifact_location": remote_uri})
            self.metadata_path(version).write_text(
                json.dumps(metadata.as_dict(), indent=2, sort_keys=True)
            )
        return metadata

    def _should_sync_remote(self) -> bool:
        from ml.collaborative.object_store import sync_enabled

        return sync_enabled()

    def ensure_local(self, version: str) -> None:
        """Ensure ``version`` exists in the local cache, downloading from S3 if needed."""
        if self.has_version(version):
            return
        if not self._should_sync_remote():
            return
        from ml.collaborative.object_store import download_version_directory

        download_version_directory(version=version, local_dir=self.artifact_dir(version))

    def load_metadata(self, version: str) -> ArtifactMetadata:
        self.ensure_local(version)
        payload = json.loads(self.metadata_path(version).read_text())
        payload.setdefault("model_name", CF_MODEL_NAME)
        payload.setdefault("dataset_version", "")
        payload.setdefault(
            "artifact_location",
            str(self.artifact_dir(version).resolve()),
        )
        return ArtifactMetadata(**payload)

    def load_model(self, version: str, *, model_cls) -> CollaborativeFilteringModel:
        self.ensure_local(version)
        model_path = self.model_path(version)
        if not model_path.is_file():
            raise FileNotFoundError(f"CF artifact missing for version {version!r} at {model_path}")
        return model_cls.load(model_path)

    def has_version(self, version: str) -> bool:
        return self.model_path(version).is_file() and self.metadata_path(version).is_file()

    def build_index_maps(
        self,
        metadata: ArtifactMetadata,
    ) -> tuple[dict[UUID, int], dict[UUID, int], dict[int, UUID]]:
        user_index = {UUID(user_id): idx for idx, user_id in enumerate(metadata.user_ids)}
        item_index = {UUID(item_id): idx for idx, item_id in enumerate(metadata.item_ids)}
        reverse_item_index = {idx: UUID(item_id) for idx, item_id in enumerate(metadata.item_ids)}
        return user_index, item_index, reverse_item_index
