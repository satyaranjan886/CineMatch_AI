import django_filters

from apps.movies.models import Genre, Movie


class MovieFilter(django_filters.FilterSet):
    genre = django_filters.CharFilter(field_name="movie_genres__genre__slug", distinct=True)
    genre_id = django_filters.UUIDFilter(field_name="movie_genres__genre_id", distinct=True)
    year = django_filters.NumberFilter(field_name="release_date__year")
    min_rating = django_filters.NumberFilter(field_name="vote_average", lookup_expr="gte")
    max_rating = django_filters.NumberFilter(field_name="vote_average", lookup_expr="lte")
    status = django_filters.ChoiceFilter(choices=Movie._meta.get_field("status").choices)
    language = django_filters.CharFilter(field_name="language", lookup_expr="iexact")
    country = django_filters.CharFilter(field_name="country", lookup_expr="iexact")

    class Meta:
        model = Movie
        fields: list[str] = []


class GenreFilter(django_filters.FilterSet):
    name = django_filters.CharFilter(field_name="name", lookup_expr="icontains")

    class Meta:
        model = Genre
        fields = ["name"]
