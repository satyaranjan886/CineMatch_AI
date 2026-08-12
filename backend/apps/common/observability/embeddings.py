"""Embedding provider that records inference metrics."""

from __future__ import annotations

from ml.embeddings.provider import EmbeddingProvider


class InstrumentedEmbeddingProvider(EmbeddingProvider):
    def __init__(self, provider: EmbeddingProvider, *, model_name: str):
        self._provider = provider
        self.model_name = model_name

    def generate_embedding(self, text: str) -> list[float]:
        from apps.common.observability.metrics import observe_inference

        with observe_inference(model=f"embedding:{self.model_name}"):
            return self._provider.generate_embedding(text)

    def generate_batch_embeddings(self, texts: list[str]) -> list[list[float]]:
        from apps.common.observability.metrics import observe_inference

        with observe_inference(model=f"embedding:{self.model_name}"):
            return self._provider.generate_batch_embeddings(texts)

    def __getattr__(self, item):
        return getattr(self._provider, item)
