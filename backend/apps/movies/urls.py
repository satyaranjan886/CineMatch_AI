from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.movies.views import GenreViewSet, MovieViewSet

router = DefaultRouter()
router.register("movies", MovieViewSet, basename="movie")
router.register("genres", GenreViewSet, basename="genre")

urlpatterns = [
    path("", include(router.urls)),
]
