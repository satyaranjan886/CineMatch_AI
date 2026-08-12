"""Content-based recommendation primitives."""

from ml.content_based.features import MovieFeatureBuilder, MovieFeatures
from ml.content_based.index import ContentSimilarityIndex
from ml.content_based.profile import (
    UserContentProfile,
    UserContentProfileService,
    WeightedMovieSignal,
)
from ml.content_based.tfidf import SimilarityMatch, TfidfSimilarityEngine

__all__ = [
    "ContentSimilarityIndex",
    "MovieFeatureBuilder",
    "MovieFeatures",
    "SimilarityMatch",
    "TfidfSimilarityEngine",
    "UserContentProfile",
    "UserContentProfileService",
    "WeightedMovieSignal",
]
