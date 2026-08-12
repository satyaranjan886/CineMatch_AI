"""Embedding provider factory."""

from __future__ import annotations

from django.conf import settings
from django.utils.module_loading import import_string

from apps.common.observability.embeddings import InstrumentedEmbeddingProvider
from ml.embeddings.provider import EmbeddingProvider


def get_embedding_provider(*, model_name: str | None = None) -> EmbeddingProvider:
    provider_path = getattr(
        settings,
        "EMBEDDING_PROVIDER_CLASS",
        "ml.embeddings.sentence_transformer.SentenceTransformerEmbeddingProvider",
    )
    provider_cls = import_string(provider_path)
    resolved_model_name = model_name or getattr(
        settings,
        "EMBEDDING_MODEL_NAME",
        "sentence-transformers/all-MiniLM-L6-v2",
    )
    provider = provider_cls(model_name=resolved_model_name)
    return InstrumentedEmbeddingProvider(provider, model_name=resolved_model_name)
