"use client";

import { useInfiniteQuery, useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";

import { MovieCard } from "@/components/movies/movie-card";
import { ErrorState, EmptyState } from "@/components/feedback/states";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { MovieCardSkeleton } from "@/components/ui/skeleton";
import * as moviesApi from "@/lib/api/movies";

export default function MoviesPage() {
  const [search, setSearch] = useState("");
  const [genre, setGenre] = useState("");
  const [ordering, setOrdering] = useState("-popularity");
  const [minRating, setMinRating] = useState("");

  const genresQuery = useQuery({
    queryKey: ["genres"],
    queryFn: () => moviesApi.fetchGenres(),
  });

  const moviesQuery = useInfiniteQuery({
    queryKey: ["movies", search, genre, ordering, minRating],
    initialPageParam: 1,
    queryFn: ({ pageParam }) =>
      moviesApi.fetchMovies({
        page: pageParam,
        page_size: 24,
        search: search || undefined,
        genre: genre || undefined,
        ordering,
        min_rating: minRating ? Number(minRating) : undefined,
      }),
    getNextPageParam: (lastPage) => {
      if (!lastPage.next) return undefined;
      const url = new URL(lastPage.next);
      const page = url.searchParams.get("page");
      return page ? Number(page) : undefined;
    },
  });

  const movies = useMemo(
    () => moviesQuery.data?.pages.flatMap((page) => page.results) ?? [],
    [moviesQuery.data],
  );

  return (
    <div className="mx-auto max-w-7xl space-y-8 px-4 py-10 sm:px-6 lg:px-8">
      <header>
        <h1 className="font-display text-4xl text-foreground">Movies</h1>
        <p className="mt-2 text-muted-foreground">Browse the full catalog with filters and sort.</p>
      </header>

      <form
        className="grid gap-3 rounded-xl border border-border/60 bg-card/40 p-4 md:grid-cols-4"
        onSubmit={(event) => event.preventDefault()}
      >
        <div className="md:col-span-2">
          <label htmlFor="catalog-search" className="sr-only">
            Search movies
          </label>
          <Input
            id="catalog-search"
            placeholder="Search titles…"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />
        </div>
        <div>
          <label htmlFor="genre" className="sr-only">
            Genre
          </label>
          <select
            id="genre"
            className="h-10 w-full rounded-md border border-input bg-surface px-3 text-sm"
            value={genre}
            onChange={(event) => setGenre(event.target.value)}
          >
            <option value="">All genres</option>
            {(genresQuery.data?.results ?? []).map((item) => (
              <option key={item.id} value={item.slug}>
                {item.name}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label htmlFor="ordering" className="sr-only">
            Sort
          </label>
          <select
            id="ordering"
            className="h-10 w-full rounded-md border border-input bg-surface px-3 text-sm"
            value={ordering}
            onChange={(event) => setOrdering(event.target.value)}
          >
            <option value="-popularity">Most popular</option>
            <option value="-vote_average">Highest rated</option>
            <option value="-release_date">Newest</option>
            <option value="title">Title A–Z</option>
          </select>
        </div>
        <div>
          <label htmlFor="min-rating" className="sr-only">
            Minimum rating
          </label>
          <Input
            id="min-rating"
            type="number"
            min={0}
            max={10}
            step={0.5}
            placeholder="Min rating"
            value={minRating}
            onChange={(event) => setMinRating(event.target.value)}
          />
        </div>
      </form>

      {moviesQuery.isLoading ? (
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6">
          {Array.from({ length: 12 }).map((_, index) => (
            <MovieCardSkeleton key={index} />
          ))}
        </div>
      ) : null}

      {moviesQuery.isError ? (
        <ErrorState onRetry={() => void moviesQuery.refetch()} />
      ) : null}

      {!moviesQuery.isLoading && !moviesQuery.isError && movies.length === 0 ? (
        <EmptyState title="No matches" message="Try clearing filters or searching a different title." />
      ) : null}

      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6">
        {movies.map((movie) => (
          <MovieCard key={movie.id} movie={movie} className="w-full" />
        ))}
      </div>

      {moviesQuery.hasNextPage ? (
        <div className="flex justify-center">
          <Button
            type="button"
            variant="outline"
            disabled={moviesQuery.isFetchingNextPage}
            onClick={() => void moviesQuery.fetchNextPage()}
          >
            {moviesQuery.isFetchingNextPage ? "Loading…" : "Load more"}
          </Button>
        </div>
      ) : null}
    </div>
  );
}
