"""Hybrid recommendation engine tests."""

from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest
from django.core.cache import cache
from django.utils import timezone
from rest_framework import status

from apps.accounts.models import UserPreference
from apps.interactions.models import InteractionEventType, Like, MovieInteraction, WatchHistory
from apps.recommendations.cache import (
    get_cached_home_recommendations,
    home_cache_key,
    invalidate_home_recommendations_for_user,
)
from apps.recommendations.services.hybrid import HybridHomeRecommendationService
from apps.search.services.embeddings import MovieEmbeddingService
from ml.collaborative.recommender import ActiveCollaborativeRecommender
from ml.content_based.index import ContentSimilarityIndex
from ml.pipelines.collaborative import run_collaborative_training_pipeline
from ml.ranking.diversity import rerank_with_diversity
from ml.ranking.filters import build_user_context, filter_candidates
from ml.ranking.generators import (
    GenrePreferenceCandidateGenerator,
    PopularCandidateGenerator,
    generate_candidate_pool,
)
from ml.ranking.pipeline import HybridRecommendationPipeline
from ml.ranking.pool import merge_candidates
from ml.ranking.ranker import RankingService, WeightedRankingModel
from ml.ranking.reasons import generate_reason
from ml.ranking.types import Candidate, CandidateFeatures
from tests.movies.factories import GenreFactory, MovieFactory, MovieGenreFactory


@pytest.fixture(autouse=True)
def clear_hybrid_cache():
    cache.clear()
    ContentSimilarityIndex.invalidate()
    ActiveCollaborativeRecommender.invalidate()
    yield
    cache.clear()
    ContentSimilarityIndex.invalidate()
    ActiveCollaborativeRecommender.invalidate()


@pytest.fixture
def other_user(db):
    from apps.accounts.models import User

    return User.objects.create_user(
        email="hybrid-peer@example.com",
        password="test-pass-123",
        first_name="Peer",
    )


@pytest.fixture
def hybrid_catalog(user, other_user):
    sci_fi = GenreFactory(name="Sci-Fi")
    drama = GenreFactory(name="Drama")

    anchor = MovieFactory(
        title="Interstellar",
        overview="science fiction space exploration wormhole mission",
        release_date=date(2014, 11, 7),
        vote_average=8.6,
    )
    similar_space = MovieFactory(
        title="Galaxy Quest",
        overview="science fiction space adventure comedy mission",
        release_date=date(2019, 3, 1),
        vote_average=7.8,
    )
    genre_match = MovieFactory(
        title="Gravity",
        overview="science fiction survival in space orbit",
        release_date=date(2013, 10, 4),
        vote_average=7.7,
    )
    unrelated = MovieFactory(
        title="Romantic Dinner",
        overview="restaurant love story urban romance",
        release_date=date(2010, 1, 1),
        vote_average=6.0,
    )
    disliked = MovieFactory(title="Disliked Film", overview="Disliked title")
    completed = MovieFactory(title="Completed Film", overview="Already finished")

    for movie in [anchor, similar_space, genre_match, unrelated, disliked, completed]:
        MovieGenreFactory(movie=movie, genre=sci_fi if movie != unrelated else drama)

    Like.objects.create(user=user, movie=anchor)
    Like.objects.create(user=other_user, movie=similar_space)
    Like.objects.create(user=other_user, movie=genre_match)

    MovieInteraction.objects.create(
        user=user, movie=disliked, event_type=InteractionEventType.DISLIKE
    )
    WatchHistory.objects.create(
        user=user, movie=completed, watch_percentage=100, completed_at=timezone.now()
    )
    WatchHistory.objects.create(
        user=user, movie=anchor, watch_percentage=45, last_watched_at=timezone.now()
    )

    for movie in [anchor, similar_space, genre_match, unrelated]:
        MovieEmbeddingService().generate_for_movies([movie], batch_size=4)

    preference = UserPreference.objects.get(user=user)
    preference.favorite_genres.add(sci_fi)

    return {
        "anchor": anchor,
        "similar_space": similar_space,
        "genre_match": genre_match,
        "unrelated": unrelated,
        "disliked": disliked,
        "completed": completed,
        "sci_fi": sci_fi,
    }


@pytest.mark.django_db
def test_candidate_generators_return_expected_fields(hybrid_catalog, user):
    candidates = generate_candidate_pool(user)
    assert candidates
    for candidate in candidates:
        assert candidate.movie_id
        assert candidate.source
        assert isinstance(candidate.source_score, float)


@pytest.mark.django_db
def test_merge_deduplicates_by_movie_id():
    movie_id = uuid4()
    merged = merge_candidates(
        [
            Candidate(movie_id=movie_id, source="content", source_score=0.4),
            Candidate(movie_id=movie_id, source="popular", source_score=0.9),
            Candidate(movie_id=movie_id, source="content", source_score=0.7),
        ]
    )
    assert len(merged) == 1
    features = merged[movie_id]
    assert features.content_score == 0.7
    assert features.popularity_score == 0.9


@pytest.mark.django_db
def test_filter_removes_disliked_completed_and_unavailable(hybrid_catalog, user):
    invalid = MovieFactory(title="Draft Film", status="planned")
    merged = merge_candidates(
        [
            Candidate(movie_id=hybrid_catalog["disliked"].id, source="popular", source_score=1.0),
            Candidate(movie_id=hybrid_catalog["completed"].id, source="popular", source_score=0.9),
            Candidate(
                movie_id=hybrid_catalog["similar_space"].id, source="content", source_score=0.8
            ),
            Candidate(movie_id=invalid.id, source="popular", source_score=0.95),
        ]
    )
    filtered = filter_candidates(merged, user_context=build_user_context(user))
    assert hybrid_catalog["disliked"].id not in filtered
    assert hybrid_catalog["completed"].id not in filtered
    assert invalid.id not in filtered
    assert hybrid_catalog["similar_space"].id in filtered


@pytest.mark.django_db
def test_continue_watching_not_removed_from_catalog_for_section(hybrid_catalog, user):
    user_context = build_user_context(user)
    assert hybrid_catalog["anchor"].id in user_context.continue_watching_movie_ids

    merged = merge_candidates(
        [Candidate(movie_id=hybrid_catalog["anchor"].id, source="content", source_score=0.5)]
    )
    filtered = filter_candidates(merged, user_context=user_context, exclude_completed=True)
    assert hybrid_catalog["anchor"].id in filtered


@pytest.mark.django_db
def test_ranking_service_orders_by_weighted_score():
    first_id = uuid4()
    second_id = uuid4()
    features = {
        first_id: CandidateFeatures(
            movie_id=first_id, collaborative_score=0.2, popularity_score=0.2
        ),
        second_id: CandidateFeatures(
            movie_id=second_id, collaborative_score=0.9, popularity_score=0.9
        ),
    }
    ranked = RankingService(WeightedRankingModel()).rank(features)
    assert ranked[0][0] == second_id
    assert ranked[0][1] > ranked[1][1]


@pytest.mark.django_db
def test_diversity_reduces_genre_overlap(hybrid_catalog):
    genre = hybrid_catalog["sci_fi"]
    movies = []
    for index in range(4):
        movie = MovieFactory(title=f"Sci-Fi Clone {index}", overview=f"space clone {index}")
        MovieGenreFactory(movie=movie, genre=genre)
        movies.append(movie)

    prepared = [
        (
            movie.id,
            1.0 - index * 0.05,
            CandidateFeatures(movie_id=movie.id, content_score=1.0 - index * 0.05),
            movie,
            "Similar sci-fi",
        )
        for index, movie in enumerate(movies)
    ]
    diverse = rerank_with_diversity(prepared, limit=2, lambda_relevance=0.55)
    assert len(diverse) == 2
    assert diverse[0].movie.id != diverse[1].movie.id


@pytest.mark.django_db
def test_reason_generation(hybrid_catalog, user):
    user_context = build_user_context(user)
    features = CandidateFeatures(
        movie_id=hybrid_catalog["similar_space"].id,
        genre_affinity=0.8,
        sources={"genre_preference": 0.8},
    )
    reason = generate_reason(
        features, user_context=user_context, movie=hybrid_catalog["similar_space"]
    )
    assert "favorite genres" in reason.lower() or "sci-fi" in reason.lower()


@pytest.mark.django_db
def test_cold_start_user_gets_popularity_heavy_ranking(hybrid_catalog, user):
    cold_user = user.__class__.objects.create_user(
        email="cold-hybrid@example.com",
        password="test-pass-123",
    )
    service = HybridHomeRecommendationService()
    result = service.get_home_recommendations(user=cold_user)
    section_names = [section.name for section in result.sections]
    assert "Recommended For You" in section_names
    assert "Trending Now" in section_names


@pytest.mark.django_db
def test_home_service_uses_cache(hybrid_catalog, user):
    service = HybridHomeRecommendationService()
    first = service.get_home_recommendations(user=user)
    second = service.get_home_recommendations(user=user)
    assert first.cached is False
    assert second.cached is True


@pytest.mark.django_db
def test_home_cache_invalidation_on_like(hybrid_catalog, user):
    service = HybridHomeRecommendationService()
    first = service.get_home_recommendations(user=user)
    profile = user.get_primary_profile()
    key = home_cache_key(
        user_id=user.id,
        profile_id=profile.id,
        version=first.version,
        context=first.context,
    )
    assert get_cached_home_recommendations(key) is not None

    invalidate_home_recommendations_for_user(user)
    # Epoch bump means the live key no longer hits the prior entry.
    live_key = home_cache_key(
        user_id=user.id,
        profile_id=profile.id,
        version=first.version,
        context=first.context,
    )
    assert live_key != key
    assert get_cached_home_recommendations(live_key) is None


@pytest.mark.django_db
def test_like_signal_invalidates_home_cache(hybrid_catalog, user):
    service = HybridHomeRecommendationService()
    first = service.get_home_recommendations(user=user)
    profile = user.get_primary_profile()
    key = home_cache_key(
        user_id=user.id,
        profile_id=profile.id,
        version=first.version,
        context=first.context,
    )
    assert get_cached_home_recommendations(key) is not None

    Like.objects.create(user=user, movie=hybrid_catalog["genre_match"])
    live_key = home_cache_key(
        user_id=user.id,
        profile_id=profile.id,
        version=first.version,
        context=first.context,
    )
    assert live_key != key
    assert get_cached_home_recommendations(live_key) is None


@pytest.mark.django_db
def test_home_api_returns_sections(auth_client, hybrid_catalog, user):
    response = auth_client.get("/api/v1/recommendations/home/")
    assert response.status_code == status.HTTP_200_OK
    assert response.data["version"] in {"v1", "hybrid_v1", "hybrid_v2"}
    assert response.data["cached"] is False
    names = [section["name"] for section in response.data["sections"]]
    assert names == [
        "Continue Watching",
        "Because You Watched",
        "Recommended For You",
        "Trending Now",
        "Top Rated",
        "Your Favorite Genres",
    ]
    continue_section = response.data["sections"][0]
    assert continue_section["movies"]
    assert continue_section["movies"][0]["reason"]


@pytest.mark.django_db
def test_home_api_requires_authentication(api_client):
    response = api_client.get("/api/v1/recommendations/home/")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test_deterministic_ranking_with_fixed_model(hybrid_catalog, user):
    weights = {
        "collaborative": 0.0,
        "content": 1.0,
        "genre_preference": 0.0,
        "popularity": 0.0,
        "trending": 0.0,
        "freshness": 0.0,
        "affinity": 0.0,
    }
    pipeline_service = HybridHomeRecommendationService(
        pipeline=HybridRecommendationPipeline(
            ranking_service=RankingService(WeightedRankingModel(weights=weights))
        )
    )
    first = pipeline_service.get_home_recommendations(user=user)
    second = pipeline_service.get_home_recommendations(user=user)
    first_ids = [item.movie.id for item in first.sections[2].movies]
    second_ids = [item.movie.id for item in second.sections[2].movies]
    assert first_ids == second_ids


@pytest.mark.django_db
def test_genre_preference_generator_respects_user_preferences(hybrid_catalog, user):
    generator = GenrePreferenceCandidateGenerator()
    candidates = generator.generate(user, limit=5)
    movie_ids = {candidate.movie_id for candidate in candidates}
    assert (
        hybrid_catalog["similar_space"].id in movie_ids
        or hybrid_catalog["genre_match"].id in movie_ids
    )
    assert hybrid_catalog["unrelated"].id not in movie_ids


@pytest.mark.django_db
def test_popular_generator_returns_candidates(hybrid_catalog, user):
    generator = PopularCandidateGenerator()
    candidates = generator.generate(user, limit=3)
    assert len(candidates) >= 1


@pytest.mark.django_db
def test_trained_collaborative_contributes_candidates(
    db, tmp_path, settings, user, other_user, hybrid_catalog
):
    settings.MEDIA_ROOT = tmp_path
    settings.CF_MODEL_ARTIFACT_DIR = "collaborative_models"
    settings.CF_ALS_FACTORS = 8
    settings.CF_ALS_ITERATIONS = 8
    settings.CF_MIN_USER_INTERACTIONS = 2

    movies = [MovieFactory(title=f"CF Hybrid {index}") for index in range(6)]
    for movie in movies[:3]:
        Like.objects.create(user=user, movie=movie)
    for movie in movies[3:]:
        Like.objects.create(user=other_user, movie=movie)

    run_collaborative_training_pipeline()
    candidates = generate_candidate_pool(user)
    sources = {candidate.source for candidate in candidates}
    assert "collaborative" in sources
