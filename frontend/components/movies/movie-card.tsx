"use client";

import Link from "next/link";
import { Bookmark, Heart, Play, Star } from "lucide-react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { MoviePoster } from "@/components/movies/movie-poster";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/lib/auth/auth-context";
import * as interactionsApi from "@/lib/api/interactions";
import { cn } from "@/lib/utils";
import type { Movie } from "@/types/api";

type MovieCardProps = {
  movie: Movie;
  progress?: number;
  reason?: string;
  className?: string;
};

export function MovieCard({ movie, progress, reason, className }: MovieCardProps) {
  const { isAuthenticated } = useAuth();
  const queryClient = useQueryClient();
  const year = movie.release_year ?? (movie.release_date ? movie.release_date.slice(0, 4) : null);
  const genre = movie.genres?.[0]?.name;

  const likeMutation = useMutation({
    mutationFn: () => interactionsApi.likeMovie(movie.id),
  });
  const watchlistMutation = useMutation({
    mutationFn: () => interactionsApi.addToWatchlist(movie.id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["watchlist"] });
    },
  });
  const watchMutation = useMutation({
    mutationFn: () =>
      interactionsApi.recordInteraction({
        movie_id: movie.id,
        event_type: "watch_start",
        watch_percentage: 5,
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["continue-watching"] });
      void queryClient.invalidateQueries({ queryKey: ["home-recommendations"] });
    },
  });

  return (
    <article
      className={cn(
        "group relative w-[9.5rem] shrink-0 sm:w-40 md:w-44",
        className,
      )}
    >
      <Link
        href={`/movies/${movie.id}`}
        className="block overflow-hidden rounded-lg focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
        aria-label={`${movie.title}${year ? `, ${year}` : ""}`}
        onClick={() => {
          if (!isAuthenticated) return;
          void interactionsApi.recordInteraction({
            movie_id: movie.id,
            event_type: "click",
            metadata: { surface: "movie_card" },
          });
        }}
      >
        <div className="relative aspect-[2/3] overflow-hidden rounded-lg bg-muted">
          {movie.poster_url ? (
            <MoviePoster
              src={movie.poster_url}
              alt=""
              sizes="(max-width: 640px) 152px, 176px"
              className="transition duration-500 group-hover:scale-105 group-focus-within:scale-105"
            />
          ) : (
            <div className="flex size-full items-end bg-gradient-to-br from-secondary to-background p-3">
              <span className="font-display text-sm text-foreground/80">{movie.title}</span>
            </div>
          )}
          <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-transparent to-transparent opacity-0 transition group-hover:opacity-100 group-focus-within:opacity-100" />
          {typeof progress === "number" && progress > 0 && progress < 95 ? (
            <div className="absolute inset-x-0 bottom-0 h-1 bg-black/50">
              <div
                className="h-full bg-primary"
                style={{ width: `${Math.min(100, Math.max(0, progress))}%` }}
                aria-hidden="true"
              />
            </div>
          ) : null}
          <div className="absolute inset-x-0 bottom-0 translate-y-2 p-2 opacity-0 transition group-hover:translate-y-0 group-hover:opacity-100 group-focus-within:translate-y-0 group-focus-within:opacity-100">
            {isAuthenticated ? (
              <div className="flex gap-1">
                <Button
                  type="button"
                  size="icon"
                  variant="secondary"
                  className="size-8"
                  aria-label={`Start watching ${movie.title}`}
                  onClick={(event) => {
                    event.preventDefault();
                    watchMutation.mutate();
                  }}
                >
                  <Play className="size-3.5 fill-current" />
                </Button>
                <Button
                  type="button"
                  size="icon"
                  variant="secondary"
                  className="size-8"
                  aria-label={`Like ${movie.title}`}
                  onClick={(event) => {
                    event.preventDefault();
                    likeMutation.mutate();
                  }}
                >
                  <Heart className="size-3.5" />
                </Button>
                <Button
                  type="button"
                  size="icon"
                  variant="secondary"
                  className="size-8"
                  aria-label={`Add ${movie.title} to watchlist`}
                  onClick={(event) => {
                    event.preventDefault();
                    watchlistMutation.mutate();
                  }}
                >
                  <Bookmark className="size-3.5" />
                </Button>
              </div>
            ) : null}
          </div>
        </div>
        <div className="mt-2 space-y-0.5">
          <h3 className="line-clamp-2 text-sm font-medium leading-snug text-foreground">
            {movie.title}
          </h3>
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            {year ? <span>{year}</span> : null}
            {movie.vote_average ? (
              <span className="inline-flex items-center gap-0.5">
                <Star className="size-3 fill-primary text-primary" aria-hidden="true" />
                {movie.vote_average.toFixed(1)}
              </span>
            ) : null}
          </div>
          {genre ? <p className="truncate text-xs text-muted-foreground">{genre}</p> : null}
          {reason ? <p className="line-clamp-2 text-[11px] text-champagne/90">{reason}</p> : null}
        </div>
      </Link>
    </article>
  );
}
