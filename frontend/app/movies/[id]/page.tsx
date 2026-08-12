"use client";

import Image from "next/image";
import { useParams } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bookmark, Heart, Play, Star, ThumbsDown } from "lucide-react";
import { useState } from "react";

import { MovieCarousel } from "@/components/movies/movie-carousel";
import { MoviePoster } from "@/components/movies/movie-poster";
import { ErrorState } from "@/components/feedback/states";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import * as interactionsApi from "@/lib/api/interactions";
import * as moviesApi from "@/lib/api/movies";
import { useAuth } from "@/lib/auth/auth-context";

export default function MovieDetailPage() {
  const params = useParams<{ id: string }>();
  const movieId = params.id;
  const { isAuthenticated } = useAuth();
  const queryClient = useQueryClient();
  const [rating, setRating] = useState("8");

  const movieQuery = useQuery({
    queryKey: ["movie", movieId],
    queryFn: () => moviesApi.fetchMovie(movieId),
    enabled: Boolean(movieId),
  });

  const similarQuery = useQuery({
    queryKey: ["similar", movieId],
    queryFn: () => moviesApi.fetchSimilarMovies(movieId),
    enabled: Boolean(movieId),
  });

  const likeMutation = useMutation({
    mutationFn: () => interactionsApi.likeMovie(movieId),
  });
  const dislikeMutation = useMutation({
    mutationFn: () =>
      interactionsApi.recordInteraction({ movie_id: movieId, event_type: "dislike" }),
  });
  const watchlistMutation = useMutation({
    mutationFn: () => interactionsApi.addToWatchlist(movieId),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["watchlist"] }),
  });
  const rateMutation = useMutation({
    mutationFn: () => interactionsApi.rateMovie(movieId, Number(rating)),
  });
  const watchMutation = useMutation({
    mutationFn: () =>
      interactionsApi.recordInteraction({
        movie_id: movieId,
        event_type: "watch_start",
        watch_percentage: 5,
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["home-recommendations"] });
      void queryClient.invalidateQueries({ queryKey: ["continue-watching"] });
    },
  });

  if (movieQuery.isLoading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-[50vh] w-full rounded-none" />
        <div className="mx-auto max-w-7xl px-4">
          <Skeleton className="h-10 w-1/2" />
          <Skeleton className="mt-4 h-24 w-full" />
        </div>
      </div>
    );
  }

  if (movieQuery.isError || !movieQuery.data) {
    return (
      <div className="mx-auto max-w-7xl px-4 py-16">
        <ErrorState title="Movie unavailable" onRetry={() => void movieQuery.refetch()} />
      </div>
    );
  }

  const movie = movieQuery.data;
  const directors = movie.directors?.map((item) => item.director.name).join(", ");
  const cast = movie.actors?.slice(0, 8) ?? [];
  const reason =
    similarQuery.data?.[0]?.similarity_score != null
      ? `Recommended because it is similar to titles like ${movie.title}`
      : "Recommended from content similarity";

  return (
    <div>
      <section className="relative min-h-[58vh] overflow-hidden">
        {movie.backdrop_url ? (
          <Image
            src={movie.backdrop_url}
            alt=""
            fill
            priority
            unoptimized
            className="object-cover"
            sizes="100vw"
          />
        ) : (
          <div className="absolute inset-0 bg-gradient-to-br from-secondary to-background" />
        )}
        <div className="absolute inset-0 bg-gradient-to-t from-background via-background/80 to-background/20" />
        <div className="relative mx-auto flex max-w-7xl flex-col gap-8 px-4 pb-12 pt-28 sm:flex-row sm:items-end sm:px-6 lg:px-8">
          <div className="relative aspect-[2/3] w-40 shrink-0 overflow-hidden rounded-xl border border-border/60 shadow-2xl sm:w-52">
            <MoviePoster src={movie.poster_url} alt={`${movie.title} poster`} sizes="208px" priority />
          </div>
          <div className="min-w-0 flex-1">
            <h1 className="font-display text-4xl text-foreground md:text-5xl">{movie.title}</h1>
            <div className="mt-3 flex flex-wrap items-center gap-3 text-sm text-muted-foreground">
              {movie.release_year ? <span>{movie.release_year}</span> : null}
              {movie.runtime ? <span>{movie.runtime} min</span> : null}
              <span className="inline-flex items-center gap-1">
                <Star className="size-4 fill-primary text-primary" aria-hidden="true" />
                {movie.vote_average?.toFixed(1)} ({movie.vote_count} votes)
              </span>
            </div>
            <div className="mt-3 flex flex-wrap gap-2">
              {movie.genres.map((genre) => (
                <span key={genre.id} className="rounded-full border border-border/70 px-3 py-1 text-xs text-champagne">
                  {genre.name}
                </span>
              ))}
            </div>
            {movie.tagline ? <p className="mt-4 italic text-muted-foreground">{movie.tagline}</p> : null}
            <p className="mt-4 max-w-3xl text-sm leading-relaxed text-foreground/90 md:text-base">
              {movie.overview}
            </p>
            <dl className="mt-4 grid gap-2 text-sm text-muted-foreground sm:grid-cols-2">
              {directors ? (
                <div>
                  <dt className="text-xs uppercase tracking-wide">Director</dt>
                  <dd className="text-foreground">{directors}</dd>
                </div>
              ) : null}
              {movie.release_date ? (
                <div>
                  <dt className="text-xs uppercase tracking-wide">Release date</dt>
                  <dd className="text-foreground">{movie.release_date}</dd>
                </div>
              ) : null}
            </dl>

            {isAuthenticated ? (
              <div className="mt-6 flex flex-wrap items-center gap-2">
                <Button type="button" onClick={() => watchMutation.mutate()} disabled={watchMutation.isPending}>
                  <Play className="size-4 fill-current" />
                  Start Watching
                </Button>
                <Button type="button" variant="outline" onClick={() => likeMutation.mutate()}>
                  <Heart className="size-4" />
                  Like
                </Button>
                <Button type="button" variant="outline" onClick={() => dislikeMutation.mutate()}>
                  <ThumbsDown className="size-4" />
                  Dislike
                </Button>
                <Button type="button" variant="outline" onClick={() => watchlistMutation.mutate()}>
                  <Bookmark className="size-4" />
                  Add to Watchlist
                </Button>
                <div className="flex items-center gap-2">
                  <label htmlFor="rating" className="sr-only">
                    Rating
                  </label>
                  <Input
                    id="rating"
                    type="number"
                    min={0.5}
                    max={10}
                    step={0.5}
                    className="w-20"
                    value={rating}
                    onChange={(event) => setRating(event.target.value)}
                  />
                  <Button type="button" variant="secondary" onClick={() => rateMutation.mutate()}>
                    Rate
                  </Button>
                </div>
              </div>
            ) : (
              <p className="mt-6 text-sm text-muted-foreground">Sign in to like, rate, and continue watching.</p>
            )}
          </div>
        </div>
      </section>

      <div className="mx-auto max-w-7xl space-y-10 px-4 py-10 sm:px-6 lg:px-8">
        {cast.length ? (
          <section aria-labelledby="cast-heading">
            <h2 id="cast-heading" className="font-display text-2xl text-foreground">
              Cast
            </h2>
            <ul className="mt-4 grid gap-3 sm:grid-cols-2 md:grid-cols-4">
              {cast.map((item) => (
                <li key={`${item.actor.id}-${item.character_name}`} className="rounded-lg border border-border/50 bg-card/40 p-3">
                  <p className="font-medium text-foreground">{item.actor.name}</p>
                  <p className="text-xs text-muted-foreground">{item.character_name}</p>
                </li>
              ))}
            </ul>
          </section>
        ) : null}

        <section aria-labelledby="because-heading" className="rounded-xl border border-border/60 bg-card/40 p-5">
          <h2 id="because-heading" className="font-display text-2xl text-champagne">
            Recommended Because…
          </h2>
          <p className="mt-2 text-sm text-muted-foreground">{reason}</p>
        </section>

        <MovieCarousel
          title="Similar Movies"
          movies={similarQuery.data}
          isLoading={similarQuery.isLoading}
          isError={similarQuery.isError}
          onRetry={() => void similarQuery.refetch()}
        />
      </div>
    </div>
  );
}
