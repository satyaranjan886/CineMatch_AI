"""Recommendation services."""

from apps.recommendations.services.collaborative import CollaborativeRecommendationService
from apps.recommendations.services.content_profile import UserContentProfileService
from apps.recommendations.services.hybrid import HybridHomeRecommendationService
from apps.recommendations.services.popularity import PopularityRecommendationService
from apps.recommendations.services.trending import TrendingRecommendationService

__all__ = [
    "CollaborativeRecommendationService",
    "ContentProfileService",
    "HybridHomeRecommendationService",
    "PopularityRecommendationService",
    "TrendingRecommendationService",
    "UserContentProfileService",
]

# Backwards-compatible alias
ContentProfileService = UserContentProfileService
