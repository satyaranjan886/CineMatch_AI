import { apiRequest } from "@/lib/api/client";
import type { Paginated, Rating, WatchHistoryEntry, WatchlistEntry } from "@/types/api";

export function fetchWatchHistory(page = 1) {
  return apiRequest<Paginated<WatchHistoryEntry>>("/users/me/history/", {
    query: { page },
  });
}

export function fetchWatchlist(page = 1) {
  return apiRequest<Paginated<WatchlistEntry>>("/users/me/watchlist/", {
    query: { page },
  });
}

export function fetchContinueWatching() {
  return apiRequest<
    Array<{
      id: string;
      title: string;
      poster_url: string;
      watch_percentage: number;
      last_watched_at: string;
    }>
  >("/users/me/continue-watching/");
}

export function likeMovie(movieId: string) {
  return apiRequest(`/movies/${movieId}/like/`, { method: "POST", body: {} });
}

export function unlikeMovie(movieId: string) {
  return apiRequest(`/movies/${movieId}/like/`, { method: "DELETE" });
}

export function addToWatchlist(movieId: string) {
  return apiRequest(`/movies/${movieId}/watchlist/`, { method: "POST", body: {} });
}

export function removeFromWatchlist(movieId: string) {
  return apiRequest(`/movies/${movieId}/watchlist/`, { method: "DELETE" });
}

export function rateMovie(movieId: string, score: number) {
  return apiRequest<Rating>(`/movies/${movieId}/rating/`, {
    method: "POST",
    body: { score },
  });
}

export function fetchMovieRating(movieId: string) {
  return apiRequest<Rating>(`/movies/${movieId}/rating/`);
}

export function recordInteraction(payload: {
  movie_id?: string;
  event_type: string;
  watch_percentage?: number;
  metadata?: Record<string, unknown>;
  idempotency_key?: string;
}) {
  return apiRequest("/interactions/", {
    method: "POST",
    body: payload,
  });
}
