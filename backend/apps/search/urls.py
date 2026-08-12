from django.urls import path

from apps.search.views import SemanticSearchView

urlpatterns = [
    path(
        "search/semantic/",
        SemanticSearchView.as_view(),
        name="search-semantic",
    ),
]
