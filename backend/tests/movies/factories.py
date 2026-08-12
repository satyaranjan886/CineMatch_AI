import factory
from factory.django import DjangoModelFactory

from apps.movies.models import Actor, Director, Genre, Movie, MovieActor, MovieDirector, MovieGenre


class GenreFactory(DjangoModelFactory):
    class Meta:
        model = Genre

    name = factory.Sequence(lambda n: f"Genre {n}")
    slug = factory.LazyAttribute(lambda obj: obj.name.lower().replace(" ", "-"))


class ActorFactory(DjangoModelFactory):
    class Meta:
        model = Actor

    name = factory.Sequence(lambda n: f"Actor {n}")


class DirectorFactory(DjangoModelFactory):
    class Meta:
        model = Director

    name = factory.Sequence(lambda n: f"Director {n}")


class MovieFactory(DjangoModelFactory):
    class Meta:
        model = Movie

    title = factory.Sequence(lambda n: f"Movie {n}")
    overview = factory.Faker("paragraph")
    release_date = factory.Faker("date_object")
    popularity = factory.Faker("pyfloat", min_value=1, max_value=100)
    vote_average = factory.Faker("pyfloat", min_value=1, max_value=10)
    vote_count = factory.Faker("pyint", min_value=10, max_value=5000)
    status = "released"


class MovieGenreFactory(DjangoModelFactory):
    class Meta:
        model = MovieGenre

    movie = factory.SubFactory(MovieFactory)
    genre = factory.SubFactory(GenreFactory)


class MovieActorFactory(DjangoModelFactory):
    class Meta:
        model = MovieActor

    movie = factory.SubFactory(MovieFactory)
    actor = factory.SubFactory(ActorFactory)
    character_name = factory.Faker("first_name")
    billing_order = 1


class MovieDirectorFactory(DjangoModelFactory):
    class Meta:
        model = MovieDirector

    movie = factory.SubFactory(MovieFactory)
    director = factory.SubFactory(DirectorFactory)
