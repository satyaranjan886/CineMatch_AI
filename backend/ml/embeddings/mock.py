"""Deterministic embedding provider for tests."""

from __future__ import annotations

import math
import re

from ml.embeddings.provider import EmbeddingProvider

TOKEN_RE = re.compile(r"[a-z0-9_]+")


class MockEmbeddingProvider(EmbeddingProvider):
    """Bag-of-words unit vectors for fast, deterministic semantic tests."""

    def __init__(self, *, dimensions: int = 384, model_name: str = "mock-embedder"):
        self.dimensions = dimensions
        self.model_name = model_name

    def generate_embedding(self, text: str) -> list[float]:
        return self._vector_for_text(text)

    def generate_batch_embeddings(self, texts: list[str]) -> list[list[float]]:
        return [self._vector_for_text(text) for text in texts]

    def _vector_for_text(self, text: str) -> list[float]:
        values = [0.0] * self.dimensions
        for token in TOKEN_RE.findall(text.lower()):
            index = hash(token) % self.dimensions
            values[index] += 1.0

        norm = math.sqrt(sum(value * value for value in values))
        if norm <= 0:
            return values
        return [value / norm for value in values]
