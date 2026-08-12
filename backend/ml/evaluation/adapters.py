"""Offline recommender adapters for evaluation."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections import defaultdict
from uuid import UUID

from django.conf import settings
from scipy.sparse import csr_matrix

from apps.movies.models import Movie, MovieStatus
from apps.recommendations.scoring.popularity import PopularitySignals, popularity_score
from ml.collaborative.dataset import InteractionDataset, InteractionRecord
from ml.collaborative.model import ALSCollaborativeFilteringModel
from ml.content_based.index import ContentSimilarityIndex
from ml.content_based.profile import UserContentProfile, WeightedMovieSignal
from ml.evaluation.types import EvaluationFold, TimedInteraction
from ml.ranking.diversity import rerank_with_diversity
from ml.ranking.pool import merge_candidates
from ml.ranking.ranker import RankingService, WeightedRankingModel
from ml.ranking.types import Candidate


class BaseEvaluationRecommender(ABC):
    name: str
    version: str

    @abstractmethod
    def recommend_for_users(
        self,
        *,
        fold: EvaluationFold,
        user_ids: list[UUID],
        limit: int,
    ) -> dict[UUID, list[UUID]]:
        raise NotImplementedError


class PopularityEvaluationRecommender(BaseEvaluationRecommender):
    name = "popularity"
    version = "catalog-v1"

    def recommend_for_users(
        self,
        *,
        fold: EvaluationFold,
        user_ids: list[UUID],
        limit: int,
    ) -> dict[UUID, list[UUID]]:
        ranked_movies = self._rank_movies_from_train(fold.train)
        recommendations: dict[UUID, list[UUID]] = {}
        for user_id in user_ids:
            exclude = fold.train_movie_ids(user_id)
            recommendations[user_id] = [
                movie_id for movie_id in ranked_movies if movie_id not in exclude
            ][:limit]
        return recommendations

    def _rank_movies_from_train(self, train: list[TimedInteraction]) -> list[UUID]:
        """Rank using engagement from the train fold only (no future interactions)."""
        catalog = {
            movie.id: movie
            for movie in Movie.objects.filter(status=MovieStatus.RELEASED).only(
                "id", "popularity", "vote_average"
            )
        }
        # Static catalog priors are disabled by default so evaluation cannot
        # accidentally benefit from popularity fields refreshed with future traffic.
        use_catalog_prior = bool(getattr(settings, "EVAL_USE_CATALOG_PRIOR", False))
        signals_by_movie: dict[UUID, dict] = defaultdict(
            lambda: {
                "views": 0,
                "unique_users": set(),
                "completions": 0,
                "likes": 0,
                "rating_count": 0,
                "rating_total": 0.0,
            }
        )

        for interaction in train:
            if interaction.movie_id not in catalog:
                continue
            bucket = signals_by_movie[interaction.movie_id]
            bucket["unique_users"].add(str(interaction.user_id))
            if interaction.source == "watch_complete":
                bucket["completions"] += 1
                bucket["views"] += 1
            elif interaction.source == "watch_progress":
                bucket["views"] += 1
            elif interaction.source == "like":
                bucket["likes"] += 1
            elif interaction.source == "rating":
                bucket["rating_count"] += 1
                bucket["rating_total"] += interaction.weight

        # Global average rating from train ratings only (not full DB / future).
        rating_totals = [
            (bucket["rating_total"], bucket["rating_count"])
            for bucket in signals_by_movie.values()
            if bucket["rating_count"]
        ]
        if rating_totals:
            global_average = (
                sum(total for total, _ in rating_totals) / sum(count for _, count in rating_totals)
            ) * 10.0
        else:
            global_average = 7.0

        scored: list[tuple[UUID, float]] = []
        minimum_votes = getattr(settings, "RECOMMENDATION_MIN_VOTES_PRIOR", 10.0)
        for movie_id, bucket in signals_by_movie.items():
            unique_users = len(bucket["unique_users"])
            rating_count = int(bucket["rating_count"])
            average_rating = (
                float(bucket["rating_total"]) / rating_count * 10.0
                if rating_count
                else global_average
            )
            signals = PopularitySignals(
                views=int(bucket["views"]),
                unique_users=unique_users,
                completions=int(bucket["completions"]),
                likes=int(bucket["likes"]),
                rating_count=rating_count,
                average_rating=average_rating,
                catalog_popularity=(
                    float(catalog[movie_id].popularity or 0.0) if use_catalog_prior else 0.0
                ),
                catalog_vote_average=(
                    float(catalog[movie_id].vote_average or 0.0) if use_catalog_prior else 0.0
                ),
                days_since_last_event=None,
            )
            scored.append(
                (
                    movie_id,
                    popularity_score(
                        signals,
                        minimum_votes=minimum_votes,
                        global_average=global_average,
                    ),
                )
            )

        scored.sort(key=lambda item: item[1], reverse=True)
        return [movie_id for movie_id, _ in scored]


class ContentEvaluationRecommender(BaseEvaluationRecommender):
    name = "content_based"
    version = "tfidf-v1"

    def recommend_for_users(
        self,
        *,
        fold: EvaluationFold,
        user_ids: list[UUID],
        limit: int,
    ) -> dict[UUID, list[UUID]]:
        index = ContentSimilarityIndex.get()
        recommendations: dict[UUID, list[UUID]] = {}
        for user_id in user_ids:
            profile = self._build_profile(user_id, fold.train_by_user.get(user_id, []), index)
            exclude = fold.train_movie_ids(user_id)
            if profile.is_empty or profile.vector is None:
                recommendations[user_id] = []
                continue
            matches = index.engine.similar_to_vector(profile.vector, limit=limit + len(exclude))
            ranked = [match.movie_id for match in matches if match.movie_id not in exclude][:limit]
            recommendations[user_id] = ranked
        return recommendations

    def _build_profile(
        self,
        user_id: UUID,
        interactions: list[TimedInteraction],
        index: ContentSimilarityIndex,
    ) -> UserContentProfile:
        if not interactions:
            return UserContentProfile(user_id=user_id, vector=None, signals=[])

        signals = [
            WeightedMovieSignal(
                movie_id=interaction.movie_id,
                weight=interaction.weight,
                source=interaction.source,
            )
            for interaction in interactions
        ]
        vectors = []
        weights = []
        for signal in signals:
            vector = index.get_vector(signal.movie_id)
            if vector is None:
                continue
            vectors.append(vector)
            weights.append(signal.weight)
        if not vectors:
            return UserContentProfile(user_id=user_id, vector=None, signals=signals)
        profile_vector = index.engine.weighted_average_vector(vectors, weights)
        return UserContentProfile(user_id=user_id, vector=profile_vector, signals=signals)


class CollaborativeEvaluationRecommender(BaseEvaluationRecommender):
    name = "collaborative_filtering"
    version = "als-v1"

    def __init__(
        self,
        *,
        factors: int | None = None,
        iterations: int | None = None,
        random_state: int | None = None,
    ):
        self.factors = factors or getattr(settings, "CF_ALS_FACTORS", 64)
        self.iterations = iterations or getattr(settings, "CF_ALS_ITERATIONS", 15)
        self.regularization = getattr(settings, "CF_ALS_REGULARIZATION", 0.01)
        self.random_state = (
            random_state
            if random_state is not None
            else getattr(settings, "CF_ALS_RANDOM_STATE", 42)
        )

    def recommend_for_users(
        self,
        *,
        fold: EvaluationFold,
        user_ids: list[UUID],
        limit: int,
    ) -> dict[UUID, list[UUID]]:
        dataset = self._build_dataset(fold.train)
        if dataset.user_count == 0 or dataset.item_count == 0:
            return {user_id: [] for user_id in user_ids}

        model = ALSCollaborativeFilteringModel(
            factors=self.factors,
            iterations=self.iterations,
            regularization=self.regularization,
            random_state=self.random_state,
        )
        model.fit(dataset.matrix)

        recommendations: dict[UUID, list[UUID]] = {}
        for user_id in user_ids:
            user_idx = dataset.user_index.get(user_id)
            if user_idx is None:
                recommendations[user_id] = []
                continue
            exclude = fold.train_movie_ids(user_id)
            exclude_indices = {
                dataset.item_index[movie_id]
                for movie_id in exclude
                if movie_id in dataset.item_index
            }
            candidates = model.recommend(
                user_idx,
                dataset.matrix[user_idx],
                limit=limit + len(exclude_indices),
            )
            ranked: list[UUID] = []
            for candidate in candidates:
                movie_id = dataset.item_ids[candidate.item_index]
                if movie_id in exclude:
                    continue
                ranked.append(movie_id)
                if len(ranked) >= limit:
                    break
            recommendations[user_id] = ranked
        return recommendations

    def _build_dataset(self, train: list[TimedInteraction]) -> InteractionDataset:
        records = [
            InteractionRecord(
                user_id=interaction.user_id,
                movie_id=interaction.movie_id,
                weight=interaction.weight,
                source=interaction.source,
            )
            for interaction in train
        ]
        dataset = InteractionDataset(matrix=csr_matrix((0, 0)), user_ids=[], item_ids=[])
        dataset.build_matrix_from_records(records)
        return dataset


class HybridEvaluationRecommender(BaseEvaluationRecommender):
    name = "hybrid"
    version = "weighted-v1"

    def __init__(self, *, seed: int | None = None):
        random_state = seed if seed is not None else getattr(settings, "CF_ALS_RANDOM_STATE", 42)
        self.popularity = PopularityEvaluationRecommender()
        self.content = ContentEvaluationRecommender()
        self.collaborative = CollaborativeEvaluationRecommender(
            factors=min(getattr(settings, "CF_ALS_FACTORS", 64), 16),
            iterations=min(getattr(settings, "CF_ALS_ITERATIONS", 15), 10),
            random_state=random_state,
        )
        self.ranking_service = RankingService(WeightedRankingModel())

    def recommend_for_users(
        self,
        *,
        fold: EvaluationFold,
        user_ids: list[UUID],
        limit: int,
    ) -> dict[UUID, list[UUID]]:
        popularity = self.popularity.recommend_for_users(fold=fold, user_ids=user_ids, limit=100)
        content = self.content.recommend_for_users(fold=fold, user_ids=user_ids, limit=100)
        collaborative = self.collaborative.recommend_for_users(
            fold=fold, user_ids=user_ids, limit=100
        )

        recommendations: dict[UUID, list[UUID]] = {}
        for user_id in user_ids:
            candidates: list[Candidate] = []
            for index, movie_id in enumerate(popularity.get(user_id, [])):
                score = 1.0 - (index * 0.01)
                candidates.append(
                    Candidate(movie_id=movie_id, source="popular", source_score=score)
                )
            for index, movie_id in enumerate(content.get(user_id, [])):
                score = 1.0 - (index * 0.01)
                candidates.append(
                    Candidate(movie_id=movie_id, source="content", source_score=score)
                )
            for index, movie_id in enumerate(collaborative.get(user_id, [])):
                score = 1.0 - (index * 0.01)
                candidates.append(
                    Candidate(movie_id=movie_id, source="collaborative", source_score=score)
                )

            merged = merge_candidates(candidates)
            ranked = self.ranking_service.rank(merged)
            movie_ids = [movie_id for movie_id, _, _ in ranked]
            movies = {
                movie.id: movie
                for movie in Movie.objects.filter(id__in=movie_ids).prefetch_related(
                    "movie_genres__genre"
                )
            }
            prepared = [
                (
                    movie_id,
                    score,
                    features,
                    movies[movie_id],
                    "Recommended from hybrid evaluation",
                )
                for movie_id, score, features in ranked
                if movie_id in movies and movie_id not in fold.train_movie_ids(user_id)
            ]
            diverse = rerank_with_diversity(prepared, limit=limit)
            recommendations[user_id] = [item.movie.id for item in diverse]
        return recommendations


def get_recommender(model_name: str, *, seed: int | None = None) -> BaseEvaluationRecommender:
    key = model_name.strip().lower()
    if key in {"popularity"}:
        return PopularityEvaluationRecommender()
    if key in {"content", "content_based"}:
        return ContentEvaluationRecommender()
    if key in {"collaborative", "collaborative_filtering"}:
        return CollaborativeEvaluationRecommender(random_state=seed)
    if key == "hybrid":
        return HybridEvaluationRecommender(seed=seed)
    raise ValueError(f"Unknown recommender model: {model_name}")
