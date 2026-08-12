from rest_framework import serializers

from apps.movies.models import Actor, Director, Genre, Movie, MovieActor, MovieDirector


class GenreSerializer(serializers.ModelSerializer):
    class Meta:
        model = Genre
        fields = ("id", "name", "slug", "created_at", "updated_at")
        read_only_fields = fields


class GenreDetailSerializer(GenreSerializer):
    movie_count = serializers.IntegerField(read_only=True)

    class Meta(GenreSerializer.Meta):
        fields = (*GenreSerializer.Meta.fields, "movie_count")


class ActorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Actor
        fields = ("id", "name")
        read_only_fields = fields


class DirectorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Director
        fields = ("id", "name")
        read_only_fields = fields


class MovieActorSerializer(serializers.ModelSerializer):
    actor = ActorSerializer(read_only=True)

    class Meta:
        model = MovieActor
        fields = ("actor", "character_name", "billing_order")
        read_only_fields = fields


class MovieDirectorSerializer(serializers.ModelSerializer):
    director = DirectorSerializer(read_only=True)

    class Meta:
        model = MovieDirector
        fields = ("director",)
        read_only_fields = fields


class MovieListSerializer(serializers.ModelSerializer):
    genres = serializers.SerializerMethodField()
    release_year = serializers.IntegerField(read_only=True)

    class Meta:
        model = Movie
        fields = (
            "id",
            "title",
            "original_title",
            "overview",
            "tagline",
            "release_date",
            "release_year",
            "runtime",
            "language",
            "country",
            "popularity",
            "vote_average",
            "vote_count",
            "poster_url",
            "backdrop_url",
            "status",
            "genres",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields

    def get_genres(self, obj: Movie) -> list[dict]:
        return [
            {"id": link.genre_id, "name": link.genre.name, "slug": link.genre.slug}
            for link in obj.movie_genres.all()
        ]


class MovieDetailSerializer(MovieListSerializer):
    actors = MovieActorSerializer(source="movie_actors", many=True, read_only=True)
    directors = MovieDirectorSerializer(source="movie_directors", many=True, read_only=True)

    class Meta(MovieListSerializer.Meta):
        fields = MovieListSerializer.Meta.fields + ("actors", "directors")


class SimilarMovieSerializer(MovieListSerializer):
    similarity_score = serializers.FloatField(read_only=True)

    class Meta(MovieListSerializer.Meta):
        fields = MovieListSerializer.Meta.fields + ("similarity_score",)
