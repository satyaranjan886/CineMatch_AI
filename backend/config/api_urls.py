from django.urls import include, path

from apps.common.views import MetricsView, ReadinessView

urlpatterns = [
    path("health/", include("apps.common.urls")),
    path("ready/", ReadinessView.as_view(), name="ready"),
    path("metrics/", MetricsView.as_view(), name="metrics"),
    path("", include("apps.movies.urls")),
    path("auth/", include("apps.accounts.urls")),
    path("", include("apps.interactions.urls")),
    path("", include("apps.recommendations.urls")),
    path("", include("apps.search.urls")),
    path("", include("apps.analytics.urls")),
    path("", include("apps.experiments.urls")),
]
