from django.urls import path

from apps.recommendations.views import (
    CollaborativeRecommendationsView,
    HomeRecommendationsView,
    PopularRecommendationsView,
    TrendingRecommendationsView,
)

urlpatterns = [
    path(
        "recommendations/popular/",
        PopularRecommendationsView.as_view(),
        name="recommendations-popular",
    ),
    path(
        "recommendations/trending/",
        TrendingRecommendationsView.as_view(),
        name="recommendations-trending",
    ),
    path(
        "recommendations/collaborative/",
        CollaborativeRecommendationsView.as_view(),
        name="recommendations-collaborative",
    ),
    path(
        "recommendations/home/",
        HomeRecommendationsView.as_view(),
        name="recommendations-home",
    ),
]
