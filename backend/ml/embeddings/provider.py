"""Embedding provider interface decoupled from any specific ML library."""

from __future__ import annotations

from abc import ABC, abstractmethod


class EmbeddingProvider(ABC):
    """Abstract embedding backend (e.g. sentence-transformers in a later phase)."""

    @abstractmethod
    def generate_embedding(self, text: str) -> list[float]:
        """Return a dense embedding for a single text document."""

    @abstractmethod
    def generate_batch_embeddings(self, texts: list[str]) -> list[list[float]]:
        """Return embeddings for a batch of documents."""


class EmbeddingProviderNotConfigured(EmbeddingProvider):
    """Placeholder used until a concrete provider is wired in."""

    def generate_embedding(self, text: str) -> list[float]:
        raise NotImplementedError(
            "No embedding provider configured. Use TF-IDF similarity or register a provider."
        )

    def generate_batch_embeddings(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError(
            "No embedding provider configured. Use TF-IDF similarity or register a provider."
        )
