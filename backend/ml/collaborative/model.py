"""Collaborative filtering model interface and ALS implementation."""

from __future__ import annotations

import pickle
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from implicit.als import AlternatingLeastSquares
from scipy.sparse import csr_matrix


@dataclass(frozen=True)
class RecommendationCandidate:
    item_index: int
    score: float


class CollaborativeFilteringModel(ABC):
    """Abstract matrix-factorization collaborative filtering backend."""

    @abstractmethod
    def fit(self, user_item_matrix: csr_matrix) -> None:
        """Train on a users x items sparse confidence matrix."""

    @abstractmethod
    def recommend(
        self,
        user_index: int,
        user_items: csr_matrix,
        *,
        limit: int = 20,
        filter_items: csr_matrix | None = None,
    ) -> list[RecommendationCandidate]:
        """Recommend item indices for a user."""

    @abstractmethod
    def save(self, path: Path) -> None:
        """Persist model artifact."""

    @classmethod
    @abstractmethod
    def load(cls, path: Path) -> CollaborativeFilteringModel:
        """Load model artifact."""


class ALSCollaborativeFilteringModel(CollaborativeFilteringModel):
    """Alternating Least Squares for implicit feedback (via `implicit`)."""

    def __init__(
        self,
        *,
        factors: int = 64,
        iterations: int = 15,
        regularization: float = 0.01,
        random_state: int = 42,
    ):
        self.factors = factors
        self.iterations = iterations
        self.regularization = regularization
        self.random_state = random_state
        self._model: AlternatingLeastSquares | None = None
        self._user_item_matrix: csr_matrix | None = None

    @property
    def is_fitted(self) -> bool:
        return self._model is not None

    def fit(self, user_item_matrix: csr_matrix) -> None:
        matrix = csr_matrix(user_item_matrix, dtype=np.float32)
        self._user_item_matrix = matrix
        model = AlternatingLeastSquares(
            factors=self.factors,
            iterations=self.iterations,
            regularization=self.regularization,
            random_state=self.random_state,
        )
        model.fit(matrix)
        self._model = model

    def recommend(
        self,
        user_index: int,
        user_items: csr_matrix,
        *,
        limit: int = 20,
        filter_items: csr_matrix | None = None,
    ) -> list[RecommendationCandidate]:
        if self._model is None:
            return []

        ids, scores = self._model.recommend(
            user_index,
            user_items,
            N=limit,
            filter_already_liked_items=True,
            filter_items=filter_items,
        )
        return [
            RecommendationCandidate(item_index=int(item_index), score=float(score))
            for item_index, score in zip(ids, scores, strict=True)
        ]

    def save(self, path: Path) -> None:
        if self._model is None:
            raise RuntimeError("Cannot save an untrained collaborative filtering model.")
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("wb") as handle:
            pickle.dump(
                {
                    "model": self._model,
                    "hyperparameters": {
                        "factors": self.factors,
                        "iterations": self.iterations,
                        "regularization": self.regularization,
                        "random_state": self.random_state,
                        "algorithm": "als",
                    },
                },
                handle,
            )

    @classmethod
    def load(cls, path: Path) -> ALSCollaborativeFilteringModel:
        with path.open("rb") as handle:
            payload = pickle.load(handle)
        hyperparameters = payload["hyperparameters"]
        instance = cls(
            factors=hyperparameters["factors"],
            iterations=hyperparameters["iterations"],
            regularization=hyperparameters["regularization"],
            random_state=hyperparameters.get("random_state", 42),
        )
        instance._model = payload["model"]
        return instance
