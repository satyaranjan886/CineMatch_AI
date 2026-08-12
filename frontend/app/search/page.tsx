"use client";

import { useQuery } from "@tanstack/react-query";
import { useDeferredValue, useMemo, useState } from "react";

import { MovieCard } from "@/components/movies/movie-card";
import { EmptyState, ErrorState } from "@/components/feedback/states";
import { Input } from "@/components/ui/input";
import { MovieCardSkeleton } from "@/components/ui/skeleton";
import * as moviesApi from "@/lib/api/movies";
import * as searchApi from "@/lib/api/search";
import type { Movie } from "@/types/api";

export default function SearchPage() {
  const [query, setQuery] = useState("");
  const [semantic, setSemantic] = useState(false);
  const [genre, setGenre] = useState("");
  const [ordering, setOrdering] = useState("-popularity");
  const deferredQuery = useDeferredValue(query.trim());

  const genresQuery = useQuery({
    queryKey: ["genres"],
    queryFn: () => moviesApi.fetchGenres(),
  });

  const autocompleteQuery = useQuery({
    queryKey: ["search-autocomplete", deferredQuery],
    queryFn: () => moviesApi.fetchMovies({ search: deferredQuery, page_size: 6 }),
    enabled: deferredQuery.length >= 2 && !semantic,
  });

  const keywordQuery = useQuery({
    queryKey: ["search-keyword", deferredQuery, genre, ordering],
    queryFn: () =>
      moviesApi.fetchMovies({
        search: deferredQuery,
        genre: genre || undefined,
        ordering,
        page_size: 24,
      }),
    enabled: deferredQuery.length >= 2 && !semantic,
  });

  const semanticQuery = useQuery({
    queryKey: ["search-semantic", deferredQuery],
    queryFn: () => searchApi.semanticSearch(deferredQuery, 24),
    enabled: deferredQuery.length >= 2 && semantic,
  });

  const results: Movie[] = useMemo(() => {
    if (semantic) return semanticQuery.data?.results ?? [];
    return keywordQuery.data?.results ?? [];
  }, [semantic, semanticQuery.data, keywordQuery.data]);

  const isLoading = semantic ? semanticQuery.isLoading : keywordQuery.isLoading;
  const isError = semantic ? semanticQuery.isError : keywordQuery.isError;
  const refetch = () => (semantic ? semanticQuery.refetch() : keywordQuery.refetch());

  return (
    <div className="mx-auto max-w-7xl space-y-8 px-4 py-10 sm:px-6 lg:px-8">
      <header>
        <h1 className="font-display text-4xl">Search</h1>
        <p className="mt-2 text-muted-foreground">
          Keyword filters for precise browsing, or semantic search for natural-language discovery.
        </p>
      </header>

      <div className="space-y-3 rounded-xl border border-border/60 bg-card/40 p-4">
        <label htmlFor="search-input" className="sr-only">
          Search movies
        </label>
        <Input
          id="search-input"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder={semantic ? "Describe a mood or story…" : "Search by title or overview…"}
          autoComplete="off"
          aria-autocomplete="list"
          aria-controls="autocomplete-list"
        />
        {!semantic && deferredQuery.length >= 2 && (autocompleteQuery.data?.results?.length ?? 0) > 0 ? (
          <ul
            id="autocomplete-list"
            className="rounded-md border border-border/60 bg-surface p-2"
            role="listbox"
            aria-label="Suggestions"
          >
            {autocompleteQuery.data?.results.map((movie) => (
              <li key={movie.id}>
                <button
                  type="button"
                  className="w-full rounded px-2 py-2 text-left text-sm hover:bg-accent"
                  onClick={() => setQuery(movie.title)}
                >
                  {movie.title}
                  {movie.release_year ? ` (${movie.release_year})` : ""}
                </button>
              </li>
            ))}
          </ul>
        ) : null}

        <div className="flex flex-wrap items-center gap-3">
          <label className="inline-flex items-center gap-2 text-sm text-muted-foreground">
            <input
              type="checkbox"
              checked={semantic}
              onChange={(event) => setSemantic(event.target.checked)}
              className="size-4 accent-[var(--primary)]"
            />
            Semantic search
          </label>
          {!semantic ? (
            <>
              <select
                className="h-9 rounded-md border border-input bg-surface px-2 text-sm"
                value={genre}
                onChange={(event) => setGenre(event.target.value)}
                aria-label="Filter by genre"
              >
                <option value="">All genres</option>
                {(genresQuery.data?.results ?? []).map((item) => (
                  <option key={item.id} value={item.slug}>
                    {item.name}
                  </option>
                ))}
              </select>
              <select
                className="h-9 rounded-md border border-input bg-surface px-2 text-sm"
                value={ordering}
                onChange={(event) => setOrdering(event.target.value)}
                aria-label="Sort results"
              >
                <option value="-popularity">Popular</option>
                <option value="-vote_average">Top rated</option>
                <option value="-release_date">Newest</option>
                <option value="title">Title</option>
              </select>
            </>
          ) : null}
        </div>
      </div>

      {deferredQuery.length < 2 ? (
        <EmptyState title="Start typing" message="Enter at least two characters to search the catalog." />
      ) : null}

      {isLoading ? (
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6">
          {Array.from({ length: 12 }).map((_, index) => (
            <MovieCardSkeleton key={index} />
          ))}
        </div>
      ) : null}

      {isError ? <ErrorState onRetry={() => void refetch()} /> : null}

      {!isLoading && !isError && deferredQuery.length >= 2 && results.length === 0 ? (
        <EmptyState title="No results" message="Try a different query or switch search mode." />
      ) : null}

      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6">
        {results.map((movie) => (
          <MovieCard key={movie.id} movie={movie} className="w-full" reason={movie.reason} />
        ))}
      </div>
    </div>
  );
}
