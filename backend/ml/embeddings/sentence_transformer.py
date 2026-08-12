"""Sentence-transformer embedding provider."""

from __future__ import annotations

from ml.embeddings.provider import EmbeddingProvider


class SentenceTransformerEmbeddingProvider(EmbeddingProvider):
    """Local sentence-transformers backend."""

    def __init__(self, model_name: str):
        self.model_name = model_name
        self._model = None
        self._dimensions: int | None = None

    @property
    def dimensions(self) -> int:
        if self._dimensions is None:
            self._dimensions = self._load_model().get_sentence_embedding_dimension()
        return self._dimensions

    def generate_embedding(self, text: str) -> list[float]:
        vector = self._load_model().encode(text, normalize_embeddings=True)
        return vector.tolist()

    def generate_batch_embeddings(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        vectors = self._load_model().encode(
            texts, normalize_embeddings=True, batch_size=min(len(texts), 32)
        )
        return [vector.tolist() for vector in vectors]

    def _load_model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self.model_name)
        return self._model
