"""Ranking pipeline data types."""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from apps.movies.models import Movie


@dataclass(frozen=True)
class Candidate:
    movie_id: UUID
    source: str
    source_score: float


@dataclass
class CandidateFeatures:
    movie_id: UUID
    collaborative_score: float = 0.0
    content_score: float = 0.0
    semantic_score: float = 0.0
    popularity_score: float = 0.0
    trending_score: float = 0.0
    genre_affinity: float = 0.0
    user_affinity: float = 0.0
    freshness_score: float = 0.0
    rating_quality: float = 0.0
    interaction_strength: float = 0.0
    sources: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class RankedRecommendation:
    movie: Movie
    score: float
    reason: str
    features: CandidateFeatures
    primary_source: str


@dataclass(frozen=True)
class HomeSection:
    name: str
    algorithm: str
    model_version: str
    movies: list[RankedRecommendation]


@dataclass
class HomeRecommendationResult:
    version: str
    cached: bool
    sections: list[HomeSection] = field(default_factory=list)
    context: dict = field(default_factory=dict)
