"""Normalized movie text features for content-based similarity."""

from __future__ import annotations

import re
from dataclasses import dataclass

from apps.movies.models import Movie

WHITESPACE_RE = re.compile(r"\s+")
MAX_OVERVIEW_CHARS = 400
MAX_TAGLINE_CHARS = 160
MAX_PEOPLE = 8
MAX_KEYWORDS = 20


@dataclass(frozen=True)
class MovieFeatures:
    movie_id: str
    text: str


class MovieFeatureBuilder:
    """Build a compact, field-aware text representation for a movie."""

    def build(self, movie: Movie, *, keywords: list[str] | None = None) -> MovieFeatures:
        sections: list[str] = []

        title = self._normalize(movie.title)
        if title:
            sections.append(f"title {title}")

        tagline = self._normalize(movie.tagline)[:MAX_TAGLINE_CHARS]
        if tagline:
            sections.append(f"tagline {tagline}")

        overview = self._normalize(movie.overview)[:MAX_OVERVIEW_CHARS]
        if overview:
            sections.append(f"overview {overview}")

        genre_tokens = self._genre_tokens(movie)
        if genre_tokens:
            sections.append(f"genres {' '.join(genre_tokens)}")

        actor_tokens = self._people_tokens(movie, relation="movie_actors", attr="actor")
        if actor_tokens:
            sections.append(f"actors {' '.join(actor_tokens)}")

        director_tokens = self._people_tokens(movie, relation="movie_directors", attr="director")
        if director_tokens:
            sections.append(f"directors {' '.join(director_tokens)}")

        keyword_tokens = self._keyword_tokens(movie, keywords=keywords)
        if keyword_tokens:
            sections.append(f"keywords {' '.join(keyword_tokens)}")

        language = (movie.language or "").strip().lower()
        if language:
            sections.append(f"language {language}")

        text = " ".join(sections).strip()
        if not text:
            text = f"title {self._normalize(movie.title) or 'unknown'}"

        return MovieFeatures(movie_id=str(movie.id), text=text)

    def build_batch(self, movies: list[Movie]) -> list[MovieFeatures]:
        return [self.build(movie) for movie in movies]

    def _normalize(self, value: str) -> str:
        return WHITESPACE_RE.sub(" ", value.strip().lower())

    def _tokenize_name(self, name: str) -> str:
        return self._normalize(name).replace(" ", "_")

    def _genre_tokens(self, movie: Movie) -> list[str]:
        if (
            hasattr(movie, "_prefetched_objects_cache")
            and "movie_genres" in movie._prefetched_objects_cache
        ):
            genres = [link.genre.name for link in movie.movie_genres.all()]
        else:
            genres = list(movie.movie_genres.values_list("genre__name", flat=True))
        return [f"genre_{self._tokenize_name(name)}" for name in sorted(genres)]

    def _people_tokens(self, movie: Movie, *, relation: str, attr: str) -> list[str]:
        links = getattr(movie, relation).all()
        if relation == "movie_actors":
            links = sorted(links, key=lambda row: (row.billing_order, str(row.id)))
        else:
            links = sorted(links, key=lambda row: str(row.id))
        names: list[str] = []
        for link in links[:MAX_PEOPLE]:
            person = getattr(link, attr)
            names.append(f"{attr}_{self._tokenize_name(person.name)}")
        return names

    def _keyword_tokens(self, movie: Movie, *, keywords: list[str] | None) -> list[str]:
        raw_keywords = keywords if keywords is not None else getattr(movie, "keywords", []) or []
        tokens: list[str] = []
        for keyword in raw_keywords[:MAX_KEYWORDS]:
            normalized = self._tokenize_name(str(keyword))
            if normalized:
                tokens.append(f"keyword_{normalized}")
        return tokens
