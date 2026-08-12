"""Movie feature builder tests."""

import pytest

from ml.content_based.features import MovieFeatureBuilder
from tests.movies.factories import (
    ActorFactory,
    DirectorFactory,
    GenreFactory,
    MovieActorFactory,
    MovieDirectorFactory,
    MovieFactory,
    MovieGenreFactory,
)


@pytest.mark.django_db
def test_feature_builder_includes_structured_fields():
    movie = MovieFactory(
        title="Nexus Protocol",
        tagline="Reality is negotiable",
        overview="A scientist discovers a breach between timelines.",
        language="en",
        keywords=["time travel", "thriller"],
    )
    sci_fi = GenreFactory(name="Science Fiction", slug="science-fiction")
    MovieGenreFactory(movie=movie, genre=sci_fi)
    actor = ActorFactory(name="Ada Lovelace")
    director = DirectorFactory(name="Alan Turing")
    MovieActorFactory(movie=movie, actor=actor, billing_order=1)
    MovieDirectorFactory(movie=movie, director=director)

    features = MovieFeatureBuilder().build(movie)

    assert "title nexus protocol" in features.text
    assert "genre_science_fiction" in features.text
    assert "actor_ada_lovelace" in features.text
    assert "director_alan_turing" in features.text
    assert "keyword_time_travel" in features.text
    assert "language en" in features.text


@pytest.mark.django_db
def test_feature_builder_handles_missing_metadata():
    movie = MovieFactory(title="Sparse Film", overview="", tagline="", language="")

    features = MovieFeatureBuilder().build(movie)

    assert features.text == "title sparse film"


@pytest.mark.django_db
def test_feature_builder_handles_movie_without_genres():
    movie = MovieFactory(title="No Genre Film", overview="Standalone story")

    features = MovieFeatureBuilder().build(movie)

    assert "genres" not in features.text
    assert "overview standalone story" in features.text
