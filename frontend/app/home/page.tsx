"use client";

import { useQuery } from "@tanstack/react-query";

import { RequireAuth } from "@/components/auth/require-auth";
import { MovieCarousel } from "@/components/movies/movie-carousel";
import { useAuth } from "@/lib/auth/auth-context";
import * as interactionsApi from "@/lib/api/interactions";
import * as moviesApi from "@/lib/api/movies";
import * as recommendationsApi from "@/lib/api/recommendations";
import type { Movie } from "@/types/api";

function sectionMovies(
  sections: { name: string; movies: Movie[] }[] | undefined,
  name: string,
): Movie[] {
  return sections?.find((section) => section.name === name)?.movies ?? [];
}

function HomeContent() {
  const { profile } = useAuth();

  const homeQuery = useQuery({
    queryKey: ["home-recommendations"],
    queryFn: () => recommendationsApi.fetchHomeRecommendations("web-home"),
  });

  const popularQuery = useQuery({
    queryKey: ["popular"],
    queryFn: () => recommendationsApi.fetchPopular(24),
  });

  const sciFiQuery = useQuery({
    queryKey: ["genre-movies", "sci-fi"],
    queryFn: () => moviesApi.fetchMovies({ genre: "sci-fi", page_size: 24, ordering: "-popularity" }),
  });

  const actionQuery = useQuery({
    queryKey: ["genre-movies", "action"],
    queryFn: () => moviesApi.fetchMovies({ genre: "action", page_size: 24, ordering: "-popularity" }),
  });

  const dramaQuery = useQuery({
    queryKey: ["genre-movies", "drama"],
    queryFn: () => moviesApi.fetchMovies({ genre: "drama", page_size: 24, ordering: "-popularity" }),
  });

  const continueQuery = useQuery({
    queryKey: ["continue-watching"],
    queryFn: () => interactionsApi.fetchContinueWatching(),
  });

  const sections = homeQuery.data?.sections;
  const continueWatching = sectionMovies(sections, "Continue Watching");
  const becauseYouWatched = sectionMovies(sections, "Because You Watched");
  const recommended = sectionMovies(sections, "Recommended For You");
  const trending = sectionMovies(sections, "Trending Now");
  const topRated = sectionMovies(sections, "Top Rated");

  const progressByMovieId = Object.fromEntries(
    (continueQuery.data ?? []).map((entry) => [entry.id, entry.watch_percentage]),
  );

  return (
    <div className="mx-auto max-w-7xl space-y-12 px-4 py-10 sm:px-6 lg:px-8">
      <header className="max-w-2xl">
        <p className="text-xs font-semibold uppercase tracking-[0.3em] text-primary">Tonight&apos;s reel</p>
        <h1 className="mt-2 font-display text-4xl text-foreground md:text-5xl">
          {profile?.display_name ? `For ${profile.display_name}` : "Your cinema"}
        </h1>
        <p className="mt-3 text-muted-foreground">
          Personalized rows from the hybrid engine — plus evergreen genre shelves for free exploration.
        </p>
      </header>

      <MovieCarousel
        title="Continue Watching"
        movies={continueWatching}
        isLoading={homeQuery.isLoading}
        isError={homeQuery.isError}
        onRetry={() => void homeQuery.refetch()}
        progressByMovieId={progressByMovieId}
        emptyMessage="Nothing in progress. Start a film from Recommended For You."
      />
      <MovieCarousel
        title="Because You Watched"
        movies={becauseYouWatched}
        isLoading={homeQuery.isLoading}
        isError={homeQuery.isError}
        onRetry={() => void homeQuery.refetch()}
      />
      <MovieCarousel
        title="Recommended For You"
        movies={recommended}
        isLoading={homeQuery.isLoading}
        isError={homeQuery.isError}
        onRetry={() => void homeQuery.refetch()}
      />
      <MovieCarousel
        title="Trending Now"
        movies={trending}
        isLoading={homeQuery.isLoading}
        isError={homeQuery.isError}
        onRetry={() => void homeQuery.refetch()}
      />
      <MovieCarousel
        title="Popular Movies"
        movies={popularQuery.data?.results}
        isLoading={popularQuery.isLoading}
        isError={popularQuery.isError}
        onRetry={() => void popularQuery.refetch()}
      />
      <MovieCarousel
        title="Top Rated"
        movies={topRated}
        isLoading={homeQuery.isLoading}
        isError={homeQuery.isError}
        onRetry={() => void homeQuery.refetch()}
      />
      <MovieCarousel
        title="Sci-Fi Picks"
        movies={sciFiQuery.data?.results}
        isLoading={sciFiQuery.isLoading}
        isError={sciFiQuery.isError}
        onRetry={() => void sciFiQuery.refetch()}
      />
      <MovieCarousel
        title="Action Picks"
        movies={actionQuery.data?.results}
        isLoading={actionQuery.isLoading}
        isError={actionQuery.isError}
        onRetry={() => void actionQuery.refetch()}
      />
      <MovieCarousel
        title="Drama Picks"
        movies={dramaQuery.data?.results}
        isLoading={dramaQuery.isLoading}
        isError={dramaQuery.isError}
        onRetry={() => void dramaQuery.refetch()}
      />
    </div>
  );
}

export default function HomePage() {
  return (
    <RequireAuth>
      <HomeContent />
    </RequireAuth>
  );
}
