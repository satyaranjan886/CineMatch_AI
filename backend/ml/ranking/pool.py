"""Candidate pool merge and deduplication."""

from __future__ import annotations

from uuid import UUID

from ml.ranking.types import Candidate, CandidateFeatures


def merge_candidates(candidates: list[Candidate]) -> dict[UUID, CandidateFeatures]:
    merged: dict[UUID, CandidateFeatures] = {}

    for candidate in candidates:
        features = merged.get(candidate.movie_id)
        if features is None:
            features = CandidateFeatures(movie_id=candidate.movie_id, sources={})
            merged[candidate.movie_id] = features

        features.sources[candidate.source] = max(
            features.sources.get(candidate.source, 0.0),
            candidate.source_score,
        )

        if candidate.source == "collaborative":
            features.collaborative_score = max(features.collaborative_score, candidate.source_score)
        elif candidate.source == "content":
            features.content_score = max(features.content_score, candidate.source_score)
        elif candidate.source == "semantic":
            features.semantic_score = max(features.semantic_score, candidate.source_score)
        elif candidate.source == "popular":
            features.popularity_score = max(features.popularity_score, candidate.source_score)
        elif candidate.source == "trending":
            features.trending_score = max(features.trending_score, candidate.source_score)
        elif candidate.source == "genre_preference":
            features.genre_affinity = max(features.genre_affinity, candidate.source_score)
        elif candidate.source == "recently_watched":
            features.user_affinity = max(features.user_affinity, candidate.source_score)
            features.content_score = max(features.content_score, candidate.source_score * 0.8)

    return merged
