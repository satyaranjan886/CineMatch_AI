"""Homepage section builders."""

from __future__ import annotations

from uuid import UUID

from django.conf import settings

from apps.interactions.services.continue_watching import get_continue_watching_movies
from apps.movies.models import Movie, MovieStatus
from apps.movies.services.similarity import get_similar_movies
from apps.recommendations.models import MoviePopularityScore, MovieTrendingScore
from ml.ranking.diversity import rerank_with_diversity
from ml.ranking.filters import UserRecommendationContext, build_user_context
from ml.ranking.generators import GenrePreferenceCandidateGenerator
from ml.ranking.reasons import generate_reason
from ml.ranking.types import CandidateFeatures, HomeSection, RankedRecommendation


def _to_ranked(
    movies: list[Movie],
    *,
    score: float,
    reason: str,
    source: str,
) -> list[RankedRecommendation]:
    results = []
    for movie in movies:
        features = CandidateFeatures(movie_id=movie.id, sources={source: score})
        results.append(
            RankedRecommendation(
                movie=movie,
                score=score,
                reason=reason,
                features=features,
                primary_source=source,
            )
        )
    return results


def build_continue_watching_section(user, *, limit: int = 10) -> HomeSection:
    movies = get_continue_watching_movies(user, limit=limit)
    return HomeSection(
        name="Continue Watching",
        algorithm="continue_watching",
        model_version=getattr(settings, "RECOMMENDATION_VERSION", "v1"),
        movies=_to_ranked(
            movies, score=1.0, reason="Continue where you left off", source="continue_watching"
        ),
    )


def build_because_you_watched_section(
    user,
    *,
    user_context: UserRecommendationContext | None = None,
    limit: int = 12,
) -> HomeSection:
    context = user_context or build_user_context(user)
    if not context.recent_watched_titles:
        return HomeSection(
            name="Because You Watched",
            algorithm="content_similarity",
            model_version=getattr(settings, "RECOMMENDATION_VERSION", "v1"),
            movies=[],
        )

    anchor_id = next(iter(context.recent_watched_titles))
    anchor_title = context.recent_watched_titles[anchor_id]
    similar = get_similar_movies(anchor_id, limit=limit, user=user, exclude_watched=True)
    return HomeSection(
        name="Because You Watched",
        algorithm="content_similarity",
        model_version=getattr(settings, "RECOMMENDATION_VERSION", "v1"),
        movies=[
            RankedRecommendation(
                movie=match.movie,
                score=match.score,
                reason=f"Because you watched {anchor_title}",
                features=CandidateFeatures(
                    movie_id=match.movie.id,
                    content_score=match.score,
                    sources={"recently_watched": match.score},
                ),
                primary_source="recently_watched",
            )
            for match in similar
        ],
    )


def build_recommended_for_you_section(
    user,
    *,
    ranked_pool: list[tuple[UUID, float, CandidateFeatures]],
    movies_by_id: dict[UUID, Movie],
    user_context: UserRecommendationContext,
    limit: int = 20,
) -> HomeSection:
    prepared = [
        (
            movie_id,
            score,
            features,
            movies_by_id[movie_id],
            generate_reason(features, user_context=user_context, movie=movies_by_id[movie_id]),
        )
        for movie_id, score, features in ranked_pool
        if movie_id in movies_by_id and movie_id not in user_context.continue_watching_movie_ids
    ]
    diverse = rerank_with_diversity(prepared, limit=limit)
    return HomeSection(
        name="Recommended For You",
        algorithm="hybrid_weighted",
        model_version=getattr(settings, "RECOMMENDATION_VERSION", "v1"),
        movies=diverse,
    )


def build_trending_section(*, limit: int = 12) -> HomeSection:
    window = getattr(settings, "RECOMMENDATION_TRENDING_DEFAULT_WINDOW_HOURS", 24)
    rows = list(
        MovieTrendingScore.objects.select_related("movie")
        .prefetch_related("movie__movie_genres__genre")
        .filter(movie__status=MovieStatus.RELEASED, window_hours=window)
        .order_by("-score")[:limit]
    )
    if rows:
        return HomeSection(
            name="Trending Now",
            algorithm="trending",
            model_version=getattr(settings, "RECOMMENDATION_VERSION", "v1"),
            movies=[
                RankedRecommendation(
                    movie=row.movie,
                    score=row.score,
                    reason="Trending now",
                    features=CandidateFeatures(
                        movie_id=row.movie_id,
                        trending_score=row.score,
                        sources={"trending": row.score},
                    ),
                    primary_source="trending",
                )
                for row in rows
            ],
        )

    service = __import__(
        "apps.recommendations.services.trending",
        fromlist=["TrendingRecommendationService"],
    ).TrendingRecommendationService()
    items = service.compute_scores(context={"window_hours": window})[:limit]
    return HomeSection(
        name="Trending Now",
        algorithm="trending",
        model_version=getattr(settings, "RECOMMENDATION_VERSION", "v1"),
        movies=[
            RankedRecommendation(
                movie=item.movie,
                score=item.score,
                reason="Trending now",
                features=CandidateFeatures(
                    movie_id=item.movie.id,
                    trending_score=item.score,
                    sources={"trending": item.score},
                ),
                primary_source="trending",
            )
            for item in items
        ],
    )


def build_top_rated_section(*, limit: int = 12) -> HomeSection:
    rows = list(
        MoviePopularityScore.objects.select_related("movie")
        .prefetch_related("movie__movie_genres__genre")
        .filter(movie__status=MovieStatus.RELEASED)
        .order_by("-score")[:limit]
    )
    if rows:
        return HomeSection(
            name="Top Rated",
            algorithm="popularity",
            model_version=getattr(settings, "RECOMMENDATION_VERSION", "v1"),
            movies=[
                RankedRecommendation(
                    movie=row.movie,
                    score=row.score,
                    reason="Top rated on CineMatch",
                    features=CandidateFeatures(
                        movie_id=row.movie_id,
                        popularity_score=row.score,
                        sources={"popular": row.score},
                    ),
                    primary_source="popular",
                )
                for row in rows
            ],
        )

    service = __import__(
        "apps.recommendations.services.popularity",
        fromlist=["PopularityRecommendationService"],
    ).PopularityRecommendationService()
    items = service.compute_scores()[:limit]
    return HomeSection(
        name="Top Rated",
        algorithm="popularity",
        model_version=getattr(settings, "RECOMMENDATION_VERSION", "v1"),
        movies=[
            RankedRecommendation(
                movie=item.movie,
                score=item.score,
                reason="Top rated on CineMatch",
                features=CandidateFeatures(
                    movie_id=item.movie.id,
                    popularity_score=item.score,
                    sources={"popular": item.score},
                ),
                primary_source="popular",
            )
            for item in items
        ],
    )


def build_favorite_genres_section(
    user,
    *,
    user_context: UserRecommendationContext | None = None,
    limit: int = 12,
) -> HomeSection:
    generator = GenrePreferenceCandidateGenerator()
    candidates = generator.generate(user, limit=limit)
    if not candidates:
        return HomeSection(
            name="Your Favorite Genres",
            algorithm="genre_preference",
            model_version=getattr(settings, "RECOMMENDATION_VERSION", "v1"),
            movies=[],
        )

    movies = {
        movie.id: movie
        for movie in Movie.objects.filter(
            id__in=[candidate.movie_id for candidate in candidates]
        ).prefetch_related("movie_genres__genre")
    }
    context = user_context or build_user_context(user)
    return HomeSection(
        name="Your Favorite Genres",
        algorithm="genre_preference",
        model_version=getattr(settings, "RECOMMENDATION_VERSION", "v1"),
        movies=[
            RankedRecommendation(
                movie=movies[candidate.movie_id],
                score=candidate.source_score,
                reason=generate_reason(
                    CandidateFeatures(
                        movie_id=candidate.movie_id,
                        genre_affinity=candidate.source_score,
                        sources={"genre_preference": candidate.source_score},
                    ),
                    user_context=context,
                    movie=movies[candidate.movie_id],
                ),
                features=CandidateFeatures(
                    movie_id=candidate.movie_id,
                    genre_affinity=candidate.source_score,
                    sources={"genre_preference": candidate.source_score},
                ),
                primary_source="genre_preference",
            )
            for candidate in candidates
            if candidate.movie_id in movies
        ],
    )
