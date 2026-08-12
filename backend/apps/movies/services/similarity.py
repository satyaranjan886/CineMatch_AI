"""Content-based similar movie discovery."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from apps.interactions.models import WatchHistory
from apps.movies.models import Movie
from ml.content_based.index import ContentSimilarityIndex


@dataclass(frozen=True)
class SimilarMovieResult:
    movie: Movie
    score: float


def get_similar_movies(
    movie_id: UUID,
    *,
    limit: int = 12,
    user=None,
    exclude_watched: bool = True,
) -> list[SimilarMovieResult]:
    """
    Return content-similar movies ranked by TF-IDF cosine similarity.

    When `user` is provided and `exclude_watched` is true, completed and
    in-progress watch history titles are removed from the candidate set.
    """
    index = ContentSimilarityIndex.get()
    exclude_ids = _watched_movie_ids(user) if user and exclude_watched else set()

    matches = index.similar_to(movie_id, limit=limit, exclude_ids=exclude_ids)
    results: list[SimilarMovieResult] = []
    seen: set[UUID] = set()

    for match in matches:
        if match.movie_id in seen:
            continue
        movie = index.get_movie(match.movie_id)
        if movie is None:
            continue
        seen.add(match.movie_id)
        results.append(SimilarMovieResult(movie=movie, score=match.score))
        if len(results) >= limit:
            break

    return results


def _watched_movie_ids(user) -> set[UUID]:
    return set(WatchHistory.objects.filter(user=user).values_list("movie_id", flat=True))
