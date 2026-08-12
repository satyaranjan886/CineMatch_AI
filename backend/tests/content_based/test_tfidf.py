"""TF-IDF similarity tests."""

from uuid import uuid4

import pytest

from ml.content_based.features import MovieFeatureBuilder
from ml.content_based.tfidf import TfidfSimilarityEngine
from tests.movies.factories import GenreFactory, MovieFactory, MovieGenreFactory


@pytest.mark.django_db
def test_tfidf_similarity_prefers_shared_genres():
    sci_fi = GenreFactory(name="Science Fiction", slug="science-fiction")
    comedy = GenreFactory(name="Comedy", slug="comedy")

    anchor = MovieFactory(
        title="Anchor",
        overview="A crew explores deep space anomalies",
        tagline="Beyond the void",
    )
    similar = MovieFactory(
        title="Similar",
        overview="Deep space anomalies threaten a colony",
        tagline="Void horizon",
    )
    other = MovieFactory(title="Other", overview="A family comedy in the suburbs")

    MovieGenreFactory(movie=anchor, genre=sci_fi)
    MovieGenreFactory(movie=similar, genre=sci_fi)
    MovieGenreFactory(movie=other, genre=comedy)

    builder = MovieFeatureBuilder()
    movies = [anchor, similar, other]
    features = builder.build_batch(movies)

    engine = TfidfSimilarityEngine(max_features=1000)
    engine.fit([movie.id for movie in movies], [feature.text for feature in features])

    matches = engine.similar_to(anchor.id, limit=5)
    assert matches[0].movie_id == similar.id
    assert matches[0].score > 0.0
    assert all(match.movie_id != anchor.id for match in matches)


@pytest.mark.django_db
def test_tfidf_similarity_is_deterministic():
    anchor = MovieFactory(title="Alpha", overview="Deterministic alpha story")
    candidate = MovieFactory(title="Beta", overview="Deterministic beta story")

    builder = MovieFeatureBuilder()
    movies = [anchor, candidate]
    features = builder.build_batch(movies)

    first = TfidfSimilarityEngine(max_features=1000)
    first.fit([movie.id for movie in movies], [feature.text for feature in features])
    second = TfidfSimilarityEngine(max_features=1000)
    second.fit([movie.id for movie in movies], [feature.text for feature in features])

    first_matches = first.similar_to(anchor.id, limit=5)
    second_matches = second.similar_to(anchor.id, limit=5)

    assert [(match.movie_id, round(match.score, 8)) for match in first_matches] == [
        (match.movie_id, round(match.score, 8)) for match in second_matches
    ]


def test_tfidf_similarity_unknown_movie_returns_empty():
    engine = TfidfSimilarityEngine(max_features=100)
    engine.fit([uuid4()], ["title sample movie"])

    assert engine.similar_to(uuid4(), limit=5) == []
