import { apiRequest } from "@/lib/api/client";
import type { Genre, Movie, MovieDetail, Paginated } from "@/types/api";

export type MovieListParams = {
  page?: number;
  page_size?: number;
  genre?: string;
  genre_id?: string;
  year?: number;
  min_rating?: number;
  max_rating?: number;
  language?: string;
  search?: string;
  ordering?: string;
  status?: string;
};

export function fetchMovies(params: MovieListParams = {}) {
  return apiRequest<Paginated<Movie>>("/movies/", {
    auth: false,
    query: params,
  });
}

export function fetchMovie(id: string) {
  return apiRequest<MovieDetail>(`/movies/${id}/`, { auth: false });
}

export function fetchSimilarMovies(id: string) {
  return apiRequest<Movie[]>(`/movies/${id}/similar/`, { auth: false });
}

export function fetchGenres() {
  return apiRequest<Paginated<Genre>>("/genres/", { auth: false });
}
