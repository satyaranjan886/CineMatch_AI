"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";

import { RequireAuth } from "@/components/auth/require-auth";
import { MovieCard } from "@/components/movies/movie-card";
import { EmptyState, ErrorState } from "@/components/feedback/states";
import { Button } from "@/components/ui/button";
import { MovieCardSkeleton, Skeleton } from "@/components/ui/skeleton";
import { useAuth } from "@/lib/auth/auth-context";
import * as interactionsApi from "@/lib/api/interactions";
import * as moviesApi from "@/lib/api/movies";

function ProfileContent() {
  const { user, profile, preferences } = useAuth();

  const historyQuery = useQuery({
    queryKey: ["history"],
    queryFn: () => interactionsApi.fetchWatchHistory(),
  });
  const watchlistQuery = useQuery({
    queryKey: ["watchlist"],
    queryFn: () => interactionsApi.fetchWatchlist(),
  });
  const genresQuery = useQuery({
    queryKey: ["genres"],
    queryFn: () => moviesApi.fetchGenres(),
  });

  const favoriteGenres =
    genresQuery.data?.results.filter((genre) =>
      preferences?.favorite_genre_ids?.includes(genre.id),
    ) ?? [];

  return (
    <div className="mx-auto max-w-7xl space-y-10 px-4 py-10 sm:px-6 lg:px-8">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.3em] text-primary">Profile</p>
          <h1 className="mt-2 font-display text-4xl text-foreground">
            {profile?.display_name || user?.first_name || "Viewer"}
          </h1>
          <p className="mt-2 text-muted-foreground">{user?.email}</p>
        </div>
        <Button asChild variant="outline">
          <Link href="/settings">Edit settings</Link>
        </Button>
      </header>

      <section className="grid gap-4 md:grid-cols-3">
        <div className="rounded-xl border border-border/60 bg-card/40 p-5">
          <h2 className="font-display text-xl text-champagne">Favorite genres</h2>
          {genresQuery.isLoading ? <Skeleton className="mt-3 h-8 w-full" /> : null}
          {favoriteGenres.length ? (
            <ul className="mt-3 flex flex-wrap gap-2">
              {favoriteGenres.map((genre) => (
                <li key={genre.id} className="rounded-full border border-border px-3 py-1 text-xs">
                  {genre.name}
                </li>
              ))}
            </ul>
          ) : (
            <p className="mt-3 text-sm text-muted-foreground">
              No favorite genres yet. Add them in Settings.
            </p>
          )}
        </div>
        <div className="rounded-xl border border-border/60 bg-card/40 p-5">
          <h2 className="font-display text-xl text-champagne">Languages</h2>
          <p className="mt-3 text-sm text-muted-foreground">
            {(preferences?.preferred_languages ?? []).join(", ") || "Not set"}
          </p>
        </div>
        <div className="rounded-xl border border-border/60 bg-card/40 p-5">
          <h2 className="font-display text-xl text-champagne">Decades</h2>
          <p className="mt-3 text-sm text-muted-foreground">
            {(preferences?.preferred_decades ?? []).join(", ") || "Not set"}
          </p>
        </div>
      </section>

      <section className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="font-display text-2xl">Watchlist</h2>
          <Link href="/watchlist" className="text-sm text-primary hover:underline">
            View all
          </Link>
        </div>
        {watchlistQuery.isLoading ? (
          <div className="flex gap-3 overflow-hidden">
            {Array.from({ length: 5 }).map((_, index) => (
              <MovieCardSkeleton key={index} />
            ))}
          </div>
        ) : null}
        {watchlistQuery.isError ? <ErrorState onRetry={() => void watchlistQuery.refetch()} /> : null}
        {!watchlistQuery.isLoading && (watchlistQuery.data?.results.length ?? 0) === 0 ? (
          <EmptyState title="Empty watchlist" message="Save titles while browsing." />
        ) : (
          <div className="flex gap-3 overflow-x-auto pb-2">
            {watchlistQuery.data?.results.slice(0, 8).map((entry) => (
              <MovieCard key={entry.id} movie={entry.movie} />
            ))}
          </div>
        )}
      </section>

      <section className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="font-display text-2xl">Recent history</h2>
          <Link href="/history" className="text-sm text-primary hover:underline">
            View all
          </Link>
        </div>
        {historyQuery.isLoading ? (
          <div className="flex gap-3 overflow-hidden">
            {Array.from({ length: 5 }).map((_, index) => (
              <MovieCardSkeleton key={index} />
            ))}
          </div>
        ) : null}
        {historyQuery.isError ? <ErrorState onRetry={() => void historyQuery.refetch()} /> : null}
        {!historyQuery.isLoading && (historyQuery.data?.results.length ?? 0) === 0 ? (
          <EmptyState title="No history" message="Your recently watched films will appear here." />
        ) : (
          <div className="flex gap-3 overflow-x-auto pb-2">
            {historyQuery.data?.results.slice(0, 8).map((entry) => (
              <MovieCard key={entry.id} movie={entry.movie} progress={entry.watch_percentage} />
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

export default function ProfilePage() {
  return (
    <RequireAuth>
      <ProfileContent />
    </RequireAuth>
  );
}
