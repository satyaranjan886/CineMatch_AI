"""TF-IDF vectorization and cosine similarity."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

import numpy as np
from scipy.sparse import csr_matrix
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


@dataclass
class SimilarityMatch:
    movie_id: UUID
    score: float


class TfidfSimilarityEngine:
    """Transparent baseline content similarity using TF-IDF + cosine distance."""

    def __init__(self, *, max_features: int = 5000):
        self.vectorizer = TfidfVectorizer(
            stop_words="english",
            ngram_range=(1, 2),
            min_df=1,
            sublinear_tf=True,
            max_features=max_features,
        )
        self.movie_ids: list[UUID] = []
        self.matrix: csr_matrix | None = None
        self._id_to_index: dict[UUID, int] = {}

    @property
    def is_fitted(self) -> bool:
        return self.matrix is not None and bool(self.movie_ids)

    def fit(self, movie_ids: list[UUID], texts: list[str]) -> None:
        if not movie_ids:
            self.movie_ids = []
            self.matrix = None
            self._id_to_index = {}
            return

        self.movie_ids = list(movie_ids)
        self.matrix = self.vectorizer.fit_transform(texts)
        self._id_to_index = {movie_id: idx for idx, movie_id in enumerate(self.movie_ids)}

    def transform_single(self, text: str) -> csr_matrix:
        return self.vectorizer.transform([text])

    def get_vector(self, movie_id: UUID) -> csr_matrix | None:
        if not self.is_fitted:
            return None
        index = self._id_to_index.get(movie_id)
        if index is None:
            return None
        return self.matrix[index]

    def similar_to(
        self,
        movie_id: UUID,
        *,
        limit: int = 12,
        exclude_ids: set[UUID] | None = None,
    ) -> list[SimilarityMatch]:
        exclude_ids = exclude_ids or set()
        exclude_ids.add(movie_id)

        if not self.is_fitted or movie_id not in self._id_to_index:
            return []

        source_index = self._id_to_index[movie_id]
        source_vector = self.matrix[source_index]
        scores = cosine_similarity(source_vector, self.matrix).ravel()

        matches: list[SimilarityMatch] = []
        for idx, score in enumerate(scores):
            candidate_id = self.movie_ids[idx]
            if candidate_id in exclude_ids:
                continue
            if score <= 0.0:
                continue
            matches.append(SimilarityMatch(movie_id=candidate_id, score=float(score)))

        matches.sort(key=lambda item: (-item.score, str(item.movie_id)))
        return matches[:limit]

    def similar_to_vector(
        self,
        profile_vector: csr_matrix,
        *,
        limit: int = 12,
        exclude_ids: set[UUID] | None = None,
    ) -> list[SimilarityMatch]:
        exclude_ids = exclude_ids or set()
        if not self.is_fitted:
            return []

        scores = cosine_similarity(profile_vector, self.matrix).ravel()
        matches: list[SimilarityMatch] = []
        for idx, score in enumerate(scores):
            candidate_id = self.movie_ids[idx]
            if candidate_id in exclude_ids:
                continue
            if score <= 0.0:
                continue
            matches.append(SimilarityMatch(movie_id=candidate_id, score=float(score)))

        matches.sort(key=lambda item: (-item.score, str(item.movie_id)))
        return matches[:limit]

    def weighted_average_vector(
        self,
        vectors: list[csr_matrix],
        weights: list[float],
    ) -> csr_matrix | None:
        if not vectors or not weights or len(vectors) != len(weights):
            return None

        dense = np.asarray([vector.toarray().ravel() for vector in vectors], dtype=float)
        weight_array = np.asarray(weights, dtype=float)
        if weight_array.sum() <= 0:
            return None

        averaged = np.average(dense, axis=0, weights=weight_array)
        norm = np.linalg.norm(averaged)
        if norm <= 0:
            return None
        averaged = averaged / norm
        return csr_matrix(averaged)
