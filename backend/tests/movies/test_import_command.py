import pytest
from django.core.management import call_command

from apps.movies.models import Actor, Director, Genre, Movie


@pytest.mark.django_db
def test_import_movies_sample_command():
    call_command("import_movies", "--sample", "--clear")

    assert Genre.objects.count() == 5
    assert Actor.objects.count() == 4
    assert Director.objects.count() == 3
    assert Movie.objects.count() == 5
    assert Movie.objects.filter(title="Echoes of Tomorrow").exists()
