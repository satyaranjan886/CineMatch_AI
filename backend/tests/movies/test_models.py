from datetime import date

import pytest
from django.db import IntegrityError

from apps.movies.models import MovieGenre
from tests.movies.factories import (
    GenreFactory,
    MovieActorFactory,
    MovieDirectorFactory,
    MovieFactory,
    MovieGenreFactory,
)


@pytest.mark.django_db
def test_movie_creation_with_required_fields():
    movie = MovieFactory(title="Test Film", vote_average=7.5, vote_count=100)
    assert movie.id is not None
    assert movie.title == "Test Film"
    assert movie.vote_average == 7.5


@pytest.mark.django_db
def test_movie_genre_relationship():
    link = MovieGenreFactory()
    assert link.movie.movie_genres.count() == 1
    assert link.genre.movie_genres.count() == 1


@pytest.mark.django_db
def test_movie_actor_and_director_relationships():
    actor_link = MovieActorFactory(character_name="Lead")
    MovieDirectorFactory(movie=actor_link.movie)

    movie = actor_link.movie
    assert movie.movie_actors.count() == 1
    assert movie.movie_directors.count() == 1
    assert movie.movie_actors.first().character_name == "Lead"


@pytest.mark.django_db
def test_movie_genre_unique_constraint():
    link = MovieGenreFactory()
    with pytest.raises(IntegrityError):
        MovieGenre.objects.create(movie=link.movie, genre=link.genre)


@pytest.mark.django_db
def test_genre_slug_unique():
    GenreFactory(name="Action", slug="action")
    with pytest.raises(IntegrityError):
        GenreFactory(name="Action 2", slug="action")


@pytest.mark.django_db
def test_release_year_property():
    movie = MovieFactory(release_date=date(2020, 5, 1))
    assert movie.release_year == 2020
