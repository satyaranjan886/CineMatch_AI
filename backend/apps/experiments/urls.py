from django.urls import path

from apps.experiments.views import (
    ExperimentDetailView,
    ExperimentListCreateView,
    ExperimentModelCatalogView,
    ExperimentPauseView,
    ExperimentResultsView,
    ExperimentStartView,
    ExperimentStopView,
)

urlpatterns = [
    path("experiments/", ExperimentListCreateView.as_view(), name="experiments-list"),
    path("experiments/models/", ExperimentModelCatalogView.as_view(), name="experiments-models"),
    path("experiments/<uuid:pk>/", ExperimentDetailView.as_view(), name="experiments-detail"),
    path("experiments/<uuid:pk>/start/", ExperimentStartView.as_view(), name="experiments-start"),
    path("experiments/<uuid:pk>/stop/", ExperimentStopView.as_view(), name="experiments-stop"),
    path("experiments/<uuid:pk>/pause/", ExperimentPauseView.as_view(), name="experiments-pause"),
    path(
        "experiments/<uuid:pk>/results/",
        ExperimentResultsView.as_view(),
        name="experiments-results",
    ),
]
