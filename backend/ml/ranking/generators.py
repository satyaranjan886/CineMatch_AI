"""Candidate generators for hybrid ranking."""

from __future__ import annotations

from uuid import UUID

from django.conf import settings
from django.db.models import Count, Q

from apps.accounts.models import UserPreference
from apps.interactions.models import (
    Like,
    WatchHistory,
)
from apps.movies.models import Movie, MovieStatus
from apps.movies.services.similarity import get_similar_movies
from apps.recommendations.models import MoviePopularityScore, MovieTrendingScore
from apps.search.services.similarity import SemanticSimilarityService
from ml.collaborative.recommender import ActiveCollaborativeRecommender
from ml.content_based.index import ContentSimilarityIndex
from ml.content_based.profile import UserContentProfileService
from ml.ranking.types import Candidate


def _normalize_scores(candidates: list[Candidate]) -> list[Candidate]:
    if not candidates:
        return []
    scores = [candidate.source_score for candidate in candidates]
    min_score = min(scores)
    max_score = max(scores)
    if max_score <= min_score:
        return [
            Candidate(movie_id=c.movie_id, source=c.source, source_score=1.0) for c in candidates
        ]
    return [
        Candidate(
            movie_id=candidate.movie_id,
            source=candidate.source,
            source_score=(candidate.source_score - min_score) / (max_score - min_score),
        )
        for candidate in candidates
    ]


class CandidateGenerator:
    source: str

    def generate(self, user, *, limit: int) -> list[Candidate]:
        raise NotImplementedError


class CollaborativeCandidateGenerator(CandidateGenerator):
    source = "collaborative"

    def generate(self, user, *, limit: int) -> list[Candidate]:
        recommender = ActiveCollaborativeRecommender()
        if recommender.user_interaction_count(user.id) < recommender.cold_start_threshold():
            return []
        rows = recommender.recommend_for_user(user.id, limit=limit)
        return _normalize_scores(
            [
                Candidate(movie_id=row.movie_id, source=self.source, source_score=row.score)
                for row in rows
            ]
        )


class ContentCandidateGenerator(CandidateGenerator):
    source = "content"

    def generate(self, user, *, limit: int) -> list[Candidate]:
        profile = UserContentProfileService().build_profile(user)
        if profile.is_empty or profile.vector is None:
            return []

        index = ContentSimilarityIndex.get()
        matches = index.engine.similar_to_vector(profile.vector, limit=limit)
        candidates = [
            Candidate(movie_id=match.movie_id, source=self.source, source_score=match.score)
            for match in matches
        ]
        return _normalize_scores(candidates)


class SemanticCandidateGenerator(CandidateGenerator):
    source = "semantic"

    def generate(self, user, *, limit: int) -> list[Candidate]:
        service = SemanticSimilarityService()
        liked_titles = list(
            Like.objects.filter(user=user).select_related("movie").order_by("-created_at")[:3]
        )
        if not liked_titles:
            recent = list(
                WatchHistory.objects.filter(user=user)
                .select_related("movie")
                .order_by("-last_watched_at")[:1]
            )
            if not recent:
                return []
            query = recent[0].movie.title
        else:
            query = liked_titles[0].movie.title

        matches = service.search_by_query(query, limit=limit)
        return _normalize_scores(
            [
                Candidate(movie_id=match.movie.id, source=self.source, source_score=match.score)
                for match in matches
            ]
        )


class PopularCandidateGenerator(CandidateGenerator):
    source = "popular"

    def generate(self, user, *, limit: int) -> list[Candidate]:
        rows = (
            MoviePopularityScore.objects.select_related("movie")
            .filter(movie__status=MovieStatus.RELEASED)
            .order_by("-score")[: limit * 2]
        )
        if rows:
            return _normalize_scores(
                [
                    Candidate(movie_id=row.movie_id, source=self.source, source_score=row.score)
                    for row in rows[:limit]
                ]
            )

        service = __import__(
            "apps.recommendations.services.popularity",
            fromlist=["PopularityRecommendationService"],
        ).PopularityRecommendationService()
        items = service.compute_scores()
        return _normalize_scores(
            [
                Candidate(movie_id=item.movie.id, source=self.source, source_score=item.score)
                for item in items[:limit]
            ]
        )


class TrendingCandidateGenerator(CandidateGenerator):
    source = "trending"

    def generate(self, user, *, limit: int) -> list[Candidate]:
        window = getattr(settings, "RECOMMENDATION_TRENDING_DEFAULT_WINDOW_HOURS", 24)
        rows = (
            MovieTrendingScore.objects.select_related("movie")
            .filter(movie__status=MovieStatus.RELEASED, window_hours=window)
            .order_by("-score")[:limit]
        )
        if rows:
            return _normalize_scores(
                [
                    Candidate(movie_id=row.movie_id, source=self.source, source_score=row.score)
                    for row in rows
                ]
            )

        service = __import__(
            "apps.recommendations.services.trending",
            fromlist=["TrendingRecommendationService"],
        ).TrendingRecommendationService()
        items = service.compute_scores(context={"window_hours": window})
        return _normalize_scores(
            [
                Candidate(movie_id=item.movie.id, source=self.source, source_score=item.score)
                for item in items[:limit]
            ]
        )


class GenrePreferenceCandidateGenerator(CandidateGenerator):
    source = "genre_preference"

    def generate(self, user, *, limit: int) -> list[Candidate]:
        preference = (
            UserPreference.objects.filter(user=user).prefetch_related("favorite_genres").first()
        )
        if preference is None or not preference.favorite_genres.exists():
            return []

        genre_ids = list(preference.favorite_genres.values_list("id", flat=True))
        movies = (
            Movie.objects.filter(status=MovieStatus.RELEASED, movie_genres__genre_id__in=genre_ids)
            .annotate(
                genre_matches=Count("movie_genres", filter=Q(movie_genres__genre_id__in=genre_ids))
            )
            .order_by("-genre_matches", "-vote_average", "-popularity")
            .distinct()[:limit]
        )
        if not movies:
            return []

        max_matches = max(movie.genre_matches for movie in movies)
        return _normalize_scores(
            [
                Candidate(
                    movie_id=movie.id,
                    source=self.source,
                    source_score=float(movie.genre_matches) / max(max_matches, 1),
                )
                for movie in movies
            ]
        )


class RecentlyWatchedCandidateGenerator(CandidateGenerator):
    source = "recently_watched"

    def generate(self, user, *, limit: int) -> list[Candidate]:
        recent = list(
            WatchHistory.objects.filter(user=user)
            .select_related("movie")
            .order_by("-last_watched_at")[:3]
        )
        if not recent:
            return []

        candidates: dict[UUID, Candidate] = {}
        per_anchor = max(limit // len(recent), 5)
        for entry in recent:
            similar = get_similar_movies(
                entry.movie_id, limit=per_anchor, user=user, exclude_watched=False
            )
            for match in similar:
                existing = candidates.get(match.movie.id)
                score = match.score
                if existing is None or score > existing.source_score:
                    candidates[match.movie.id] = Candidate(
                        movie_id=match.movie.id,
                        source=self.source,
                        source_score=score,
                    )
        return _normalize_scores(list(candidates.values())[:limit])


def get_candidate_generators() -> list[CandidateGenerator]:
    return [
        CollaborativeCandidateGenerator(),
        ContentCandidateGenerator(),
        SemanticCandidateGenerator(),
        PopularCandidateGenerator(),
        TrendingCandidateGenerator(),
        GenrePreferenceCandidateGenerator(),
        RecentlyWatchedCandidateGenerator(),
    ]


def generate_candidate_pool(user) -> list[Candidate]:
    limits = getattr(
        settings,
        "HYBRID_CANDIDATE_LIMITS",
        {
            "collaborative": 100,
            "content": 100,
            "semantic": 100,
            "trending": 50,
            "popular": 50,
            "genre_preference": 50,
            "recently_watched": 50,
        },
    )
    pool: list[Candidate] = []
    for generator in get_candidate_generators():
        pool.extend(generator.generate(user, limit=limits.get(generator.source, 50)))
    return pool
