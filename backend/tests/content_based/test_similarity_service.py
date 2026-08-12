"""Similar movie service tests."""

import pytest

from apps.interactions.models import WatchHistory
from apps.movies.services.similarity import get_similar_movies
from tests.movies.factories import GenreFactory, MovieFactory, MovieGenreFactory


@pytest.fixture
def content_catalog(db):
    sci_fi = GenreFactory(name="Science Fiction", slug="science-fiction")
    comedy = GenreFactory(name="Comedy", slug="comedy")

    anchor = MovieFactory(
        title="Anchor Film",
        overview="Space exploration mission to the outer rim",
        tagline="Beyond known space",
    )
    similar = MovieFactory(
        title="Similar Film",
        overview="Outer rim exploration and first contact",
        tagline="Contact event",
    )
    duplicate = MovieFactory(
        title="Similar Film Duplicate",
        overview="Outer rim exploration and first contact",
        tagline="Contact event",
    )
    other = MovieFactory(title="Other Film", overview="Suburban comedy ensemble")

    for movie in (anchor, similar, duplicate):
        MovieGenreFactory(movie=movie, genre=sci_fi)
    MovieGenreFactory(movie=other, genre=comedy)

    return {
        "anchor": anchor,
        "similar": similar,
        "duplicate": duplicate,
        "other": other,
    }


@pytest.mark.django_db
def test_get_similar_movies_orders_by_content_similarity(content_catalog):
    results = get_similar_movies(content_catalog["anchor"].id, limit=5)

    titles = [item.movie.title for item in results]
    assert "Similar Film" in titles
    assert "Other Film" not in titles[:2]
    assert results[0].score >= results[-1].score


@pytest.mark.django_db
def test_get_similar_movies_excludes_duplicates(content_catalog):
    results = get_similar_movies(content_catalog["anchor"].id, limit=10)
    movie_ids = [item.movie.id for item in results]

    assert len(movie_ids) == len(set(movie_ids))


@pytest.mark.django_db
def test_get_similar_movies_filters_watched_titles(user, content_catalog):
    watched = content_catalog["similar"]
    WatchHistory.objects.create(user=user, movie=watched, watch_percentage=80)

    results = get_similar_movies(
        content_catalog["anchor"].id,
        limit=10,
        user=user,
        exclude_watched=True,
    )
    returned_ids = {item.movie.id for item in results}

    assert watched.id not in returned_ids


@pytest.mark.django_db
def test_get_similar_movies_without_genres():
    lone = MovieFactory(title="Solo Title", overview="Unique lone storyline")
    peer = MovieFactory(title="Solo Peer", overview="Unique lone peer storyline")

    results = get_similar_movies(lone.id, limit=5)

    assert results
    assert all(result.movie.id != lone.id for result in results)
    assert results[0].movie.id in {peer.id}
