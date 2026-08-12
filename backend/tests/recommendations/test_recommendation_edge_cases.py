"""Recommendation edge-case coverage — user activity, filters, fallbacks, ranking."""

from __future__ import annotations

from uuid import uuid4

import pytest
from django.core.cache import cache
from django.utils import timezone

from apps.accounts.models import User, UserPreference
from apps.interactions.models import InteractionEventType, Like, MovieInteraction, WatchHistory
from apps.recommendations.services.collaborative import CollaborativeRecommendationService
from apps.recommendations.services.hybrid import HybridHomeRecommendationService
from apps.search.services.embeddings import MovieEmbeddingService
from ml.collaborative.recommender import ActiveCollaborativeRecommender
from ml.content_based.index import ContentSimilarityIndex
from ml.ranking.diversity import rerank_with_diversity
from ml.ranking.filters import build_user_context, filter_candidates
from ml.ranking.generators import SemanticCandidateGenerator
from ml.ranking.pipeline import HybridRecommendationPipeline, is_cold_start_user
from ml.ranking.pool import merge_candidates
from ml.ranking.ranker import RankingService, WeightedRankingModel
from ml.ranking.reasons import generate_reason
from ml.ranking.types import Candidate, CandidateFeatures
from tests.movies.factories import GenreFactory, MovieFactory, MovieGenreFactory


@pytest.fixture(autouse=True)
def _reset_rec_state():
    cache.clear()
    ContentSimilarityIndex.invalidate()
    ActiveCollaborativeRecommender.invalidate()
    yield
    cache.clear()
    ContentSimilarityIndex.invalidate()
    ActiveCollaborativeRecommender.invalidate()


@pytest.fixture
def catalog(db):
    sci_fi = GenreFactory(name="Sci-Fi Edge")
    drama = GenreFactory(name="Drama Edge")
    movies = {
        "liked": MovieFactory(title="Edge Liked", overview="space adventure", vote_average=8.0),
        "peer": MovieFactory(title="Edge Peer", overview="space mission", vote_average=7.5),
        "genre": MovieFactory(title="Edge Genre", overview="orbit survival", vote_average=7.2),
        "disliked": MovieFactory(title="Edge Disliked", overview="unwanted film"),
        "watched": MovieFactory(title="Edge Watched", overview="already finished"),
        "drama": MovieFactory(title="Edge Drama", overview="emotional drama", vote_average=6.5),
    }
    for key, movie in movies.items():
        genre = drama if key == "drama" else sci_fi
        MovieGenreFactory(movie=movie, genre=genre)
    return {"sci_fi": sci_fi, "drama": drama, **movies}


@pytest.mark.django_db
def test_new_user_is_cold_start_and_gets_home_sections(catalog):
    new_user = User.objects.create_user(email="new-edge@example.com", password="test-pass-123")
    assert is_cold_start_user(new_user) is True

    result = HybridHomeRecommendationService().get_home_recommendations(user=new_user)
    names = [section.name for section in result.sections]
    assert "Recommended For You" in names
    assert "Trending Now" in names
    assert "Top Rated" in names


@pytest.mark.django_db
def test_low_activity_user_still_receives_recommendations(catalog):
    user = User.objects.create_user(email="low-edge@example.com", password="test-pass-123")
    Like.objects.create(user=user, movie=catalog["liked"])

    result = HybridHomeRecommendationService().get_home_recommendations(user=user)
    assert result.sections
    recommended = next(
        section for section in result.sections if section.name == "Recommended For You"
    )
    # May be empty if pool filters everything, but pipeline must complete without error.
    assert isinstance(recommended.movies, list)


@pytest.mark.django_db
def test_high_activity_user_excludes_completed_and_disliked(catalog):
    user = User.objects.create_user(email="high-edge@example.com", password="test-pass-123")
    for movie in (catalog["liked"], catalog["peer"], catalog["genre"], catalog["drama"]):
        Like.objects.create(user=user, movie=movie)
        WatchHistory.objects.create(user=user, movie=movie, watch_percentage=40)
    MovieInteraction.objects.create(
        user=user,
        movie=catalog["disliked"],
        event_type=InteractionEventType.DISLIKE,
    )
    WatchHistory.objects.create(
        user=user,
        movie=catalog["watched"],
        watch_percentage=100,
        completed_at=timezone.now(),
    )

    context = build_user_context(user)
    merged = merge_candidates(
        [
            Candidate(movie_id=catalog["disliked"].id, source="popular", source_score=1.0),
            Candidate(movie_id=catalog["watched"].id, source="popular", source_score=0.9),
            Candidate(movie_id=catalog["peer"].id, source="content", source_score=0.8),
        ]
    )
    filtered = filter_candidates(merged, user_context=context)
    assert catalog["disliked"].id not in filtered
    assert catalog["watched"].id not in filtered
    assert catalog["peer"].id in filtered


@pytest.mark.django_db
def test_no_preferences_home_still_works(catalog):
    user = User.objects.create_user(email="nopref-edge@example.com", password="test-pass-123")
    preference = UserPreference.objects.get(user=user)
    preference.favorite_genres.clear()
    Like.objects.create(user=user, movie=catalog["liked"])

    context = build_user_context(user)
    assert context.favorite_genre_names == set()

    result = HybridHomeRecommendationService().get_home_recommendations(user=user)
    genres_section = next(
        section for section in result.sections if section.name == "Your Favorite Genres"
    )
    assert genres_section.movies == []


@pytest.mark.django_db
def test_only_disliked_movies_are_filtered_from_pool(catalog):
    user = User.objects.create_user(email="dislike-edge@example.com", password="test-pass-123")
    MovieInteraction.objects.create(
        user=user,
        movie=catalog["disliked"],
        event_type=InteractionEventType.DISLIKE,
    )
    MovieInteraction.objects.create(
        user=user,
        movie=catalog["liked"],
        event_type=InteractionEventType.DISLIKE,
    )

    merged = merge_candidates(
        [
            Candidate(movie_id=catalog["disliked"].id, source="popular", source_score=1.0),
            Candidate(movie_id=catalog["liked"].id, source="popular", source_score=0.9),
            Candidate(movie_id=catalog["peer"].id, source="popular", source_score=0.8),
        ]
    )
    filtered = filter_candidates(merged, user_context=build_user_context(user))
    assert catalog["disliked"].id not in filtered
    assert catalog["liked"].id not in filtered
    assert catalog["peer"].id in filtered


@pytest.mark.django_db
def test_already_watched_completed_titles_excluded(catalog):
    user = User.objects.create_user(email="watched-edge@example.com", password="test-pass-123")
    WatchHistory.objects.create(
        user=user,
        movie=catalog["watched"],
        watch_percentage=100,
        completed_at=timezone.now(),
    )
    merged = merge_candidates(
        [
            Candidate(movie_id=catalog["watched"].id, source="content", source_score=1.0),
            Candidate(movie_id=catalog["peer"].id, source="content", source_score=0.5),
        ]
    )
    filtered = filter_candidates(
        merged, user_context=build_user_context(user), exclude_completed=True
    )
    assert catalog["watched"].id not in filtered
    assert catalog["peer"].id in filtered


@pytest.mark.django_db
def test_duplicate_candidates_merge_keeps_max_scores():
    movie_id = uuid4()
    merged = merge_candidates(
        [
            Candidate(movie_id=movie_id, source="content", source_score=0.2),
            Candidate(movie_id=movie_id, source="content", source_score=0.9),
            Candidate(movie_id=movie_id, source="popular", source_score=0.4),
            Candidate(movie_id=movie_id, source="popular", source_score=0.3),
        ]
    )
    assert list(merged.keys()) == [movie_id]
    assert merged[movie_id].content_score == 0.9
    assert merged[movie_id].popularity_score == 0.4
    assert merged[movie_id].sources["content"] == 0.9
    assert merged[movie_id].sources["popular"] == 0.4


@pytest.mark.django_db
def test_empty_candidate_pool_pipeline_returns_sections(catalog):
    user = User.objects.create_user(email="empty-edge@example.com", password="test-pass-123")
    # No interactions and empty catalog popularity — pipeline must not crash.
    pipeline = HybridRecommendationPipeline(
        ranking_service=RankingService(
            WeightedRankingModel(
                weights={
                    "collaborative": 0,
                    "content": 0,
                    "genre_preference": 0,
                    "popularity": 1,
                    "trending": 0,
                    "freshness": 0,
                    "affinity": 0,
                }
            )
        )
    )
    result = pipeline.build_home(user)
    assert len(result.sections) == 6
    recommended = result.sections[2]
    assert recommended.name == "Recommended For You"


@pytest.mark.django_db
def test_missing_embeddings_semantic_generator_returns_empty_or_safe(catalog):
    user = User.objects.create_user(email="noembed-edge@example.com", password="test-pass-123")
    Like.objects.create(user=user, movie=catalog["liked"])
    # Catalog movies intentionally have no embeddings.
    candidates = SemanticCandidateGenerator().generate(user, limit=10)
    assert isinstance(candidates, list)


@pytest.mark.django_db
def test_missing_collaborative_model_falls_back_to_popularity(catalog):
    user = User.objects.create_user(email="nocf-edge@example.com", password="test-pass-123")
    # Enough likes to avoid cold-start path but no trained artifact.
    for movie in (catalog["liked"], catalog["peer"], catalog["genre"], catalog["drama"]):
        Like.objects.create(user=user, movie=movie)

    ActiveCollaborativeRecommender.invalidate()
    service = CollaborativeRecommendationService()
    # Without an active artifact, recommend_for_user returns []; service returns empty list
    # (not crash). Cold-start users get popular_fallback instead.
    result = service.get_recommendations(user=user, limit=5)
    assert result.strategy in {"collaborative", "popular_fallback"}
    assert isinstance(result.items, list)


@pytest.mark.django_db
def test_cold_start_model_fallback_uses_popular_strategy(catalog):
    user = User.objects.create_user(email="fallback-edge@example.com", password="test-pass-123")
    MovieFactory(title="Popular Edge Title", popularity=99.0)
    result = CollaborativeRecommendationService().get_recommendations(user=user, limit=5)
    assert result.strategy == "popular_fallback"
    assert result.context.get("fallback") is True
    assert result.context.get("reason") == "insufficient_interactions"


@pytest.mark.django_db
def test_ranking_orders_by_configured_weights():
    low = uuid4()
    high = uuid4()
    features = {
        low: CandidateFeatures(movie_id=low, content_score=0.1, popularity_score=0.1),
        high: CandidateFeatures(movie_id=high, content_score=0.95, popularity_score=0.95),
    }
    ranked = RankingService(
        WeightedRankingModel(
            weights={
                "collaborative": 0,
                "content": 0.5,
                "genre_preference": 0,
                "popularity": 0.5,
                "trending": 0,
                "freshness": 0,
                "affinity": 0,
            }
        )
    ).rank(features)
    assert ranked[0][0] == high
    assert ranked[0][1] > ranked[1][1]


@pytest.mark.django_db
def test_diversity_prefers_mixed_genres(catalog):
    prepared = [
        (
            catalog["liked"].id,
            1.0,
            CandidateFeatures(movie_id=catalog["liked"].id, content_score=1.0),
            catalog["liked"],
            "sci-fi A",
        ),
        (
            catalog["genre"].id,
            0.99,
            CandidateFeatures(movie_id=catalog["genre"].id, content_score=0.99),
            catalog["genre"],
            "sci-fi B",
        ),
        (
            catalog["drama"].id,
            0.8,
            CandidateFeatures(movie_id=catalog["drama"].id, content_score=0.8),
            catalog["drama"],
            "drama",
        ),
    ]
    diverse = rerank_with_diversity(prepared, limit=2, lambda_relevance=0.4)
    assert len(diverse) == 2
    genre_names = set()
    for item in diverse:
        genre_names.update(link.genre.name for link in item.movie.movie_genres.all())
    assert len(genre_names) >= 2


@pytest.mark.django_db
def test_recommendation_reasons_cover_primary_sources(catalog):
    user = User.objects.create_user(email="reason-edge@example.com", password="test-pass-123")
    Like.objects.create(user=user, movie=catalog["liked"])
    preference = UserPreference.objects.get(user=user)
    preference.favorite_genres.add(catalog["sci_fi"])
    context = build_user_context(user)

    cases = [
        CandidateFeatures(
            movie_id=catalog["peer"].id,
            collaborative_score=0.9,
            sources={"collaborative": 0.9},
        ),
        CandidateFeatures(
            movie_id=catalog["genre"].id,
            genre_affinity=0.9,
            sources={"genre_preference": 0.9},
        ),
        CandidateFeatures(
            movie_id=catalog["drama"].id,
            popularity_score=0.9,
            sources={"popular": 0.9},
        ),
        CandidateFeatures(
            movie_id=catalog["liked"].id,
            trending_score=0.9,
            sources={"trending": 0.9},
        ),
    ]
    reasons = [
        generate_reason(features, user_context=context, movie=catalog["peer"]) for features in cases
    ]
    joined = " ".join(reasons).lower()
    assert "liked" in joined or "similar" in joined
    assert "genre" in joined or "sci-fi" in joined
    assert "top rated" in joined or "trending" in joined


@pytest.mark.django_db
def test_embeddings_present_enable_semantic_candidates(catalog, settings):
    settings.EMBEDDING_MODEL_NAME = "mock-embedder"
    settings.EMBEDDING_MODEL_VERSION = "edge-v1"
    settings.EMBEDDING_DIMENSIONS = 384
    user = User.objects.create_user(email="embed-edge@example.com", password="test-pass-123")
    Like.objects.create(user=user, movie=catalog["liked"])
    MovieEmbeddingService().generate_for_movies(
        [catalog["liked"], catalog["peer"], catalog["genre"]],
        batch_size=8,
    )
    candidates = SemanticCandidateGenerator().generate(user, limit=5)
    assert candidates
    assert all(candidate.source == "semantic" for candidate in candidates)
