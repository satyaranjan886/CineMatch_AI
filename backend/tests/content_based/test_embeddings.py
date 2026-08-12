"""Embedding provider interface tests."""

import pytest

from ml.embeddings.provider import EmbeddingProviderNotConfigured


def test_embedding_provider_not_configured():
    provider = EmbeddingProviderNotConfigured()

    with pytest.raises(NotImplementedError):
        provider.generate_embedding("sample text")

    with pytest.raises(NotImplementedError):
        provider.generate_batch_embeddings(["one", "two"])
