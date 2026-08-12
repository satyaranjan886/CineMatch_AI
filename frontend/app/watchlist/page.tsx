"use client";

import { useQuery } from "@tanstack/react-query";

import { RequireAuth } from "@/components/auth/require-auth";
import { MovieCard } from "@/components/movies/movie-card";
import { EmptyState, ErrorState } from "@/components/feedback/states";
import { MovieCardSkeleton } from "@/components/ui/skeleton";
import * as interactionsApi from "@/lib/api/interactions";

function WatchlistContent() {
  const query = useQuery({
    queryKey: ["watchlist"],
    queryFn: () => interactionsApi.fetchWatchlist(),
  });

  return (
    <div className="mx-auto max-w-7xl space-y-8 px-4 py-10 sm:px-6 lg:px-8">
      <header>
        <h1 className="font-display text-4xl">Watchlist</h1>
        <p className="mt-2 text-muted-foreground">Titles you saved for later.</p>
      </header>
      {query.isLoading ? (
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6">
          {Array.from({ length: 6 }).map((_, index) => (
            <MovieCardSkeleton key={index} />
          ))}
        </div>
      ) : null}
      {query.isError ? <ErrorState onRetry={() => void query.refetch()} /> : null}
      {!query.isLoading && !query.isError && (query.data?.results.length ?? 0) === 0 ? (
        <EmptyState title="Your watchlist is empty" message="Add films from any movie page or card hover actions." />
      ) : null}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6">
        {query.data?.results.map((entry) => (
          <MovieCard key={entry.id} movie={entry.movie} className="w-full" />
        ))}
      </div>
    </div>
  );
}

export default function WatchlistPage() {
  return (
    <RequireAuth>
      <WatchlistContent />
    </RequireAuth>
  );
}
