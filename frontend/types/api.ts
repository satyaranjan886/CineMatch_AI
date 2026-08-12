export type HealthResponse = {
  status: string;
};

export type ReadinessResponse = {
  status: string;
  checks: Record<string, unknown>;
};

export type Genre = {
  id: string;
  name: string;
  slug: string;
};

export type Movie = {
  id: string;
  title: string;
  original_title: string;
  overview: string;
  tagline: string;
  release_date: string | null;
  release_year: number | null;
  runtime: number | null;
  language: string;
  country: string;
  popularity: number;
  vote_average: number;
  vote_count: number;
  poster_url: string;
  backdrop_url: string;
  status: string;
  genres: Genre[];
  created_at: string;
  updated_at: string;
  score?: number;
  reason?: string;
  primary_source?: string;
  similarity_score?: number;
};

export type MovieActor = {
  actor: { id: string; name: string };
  character_name: string;
  billing_order: number;
};

export type MovieDirector = {
  director: { id: string; name: string };
};

export type MovieDetail = Movie & {
  actors: MovieActor[];
  directors: MovieDirector[];
};

export type Paginated<T> = {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
};

export type UserProfile = {
  id: string;
  display_name: string;
  is_primary: boolean;
  avatar_url?: string;
  preferred_language?: string;
  bio?: string;
  country?: string;
  timezone?: string;
  onboarding_completed?: boolean;
  onboarding_completed_at?: string | null;
};

export type UserPreferences = {
  id?: string;
  preferred_languages: string[];
  preferred_decades: number[];
  favorite_genre_ids: string[];
  favorite_actor_ids?: string[];
  favorite_director_ids?: string[];
};

export type AuthUser = {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  date_joined?: string;
  is_staff?: boolean;
};

export type MeResponse = {
  user: AuthUser;
  profile: UserProfile | null;
  preferences: UserPreferences | null;
};

export type AuthTokens = {
  access: string;
  /** @deprecated Refresh is HttpOnly cookie-only and omitted from JSON bodies. */
  refresh?: string;
};

export type AuthResponse = AuthTokens & {
  user?: AuthUser;
};

export type RecommendationListResponse = {
  strategy: string;
  cached: boolean;
  count: number;
  results: Movie[];
  fallback?: boolean;
  reason?: string;
};

export type HomeSection = {
  name: string;
  algorithm: string;
  model_version: string;
  count: number;
  movies: Movie[];
};

export type HomeRecommendationsResponse = {
  version: string;
  cached: boolean;
  sections: HomeSection[];
};

export type WatchHistoryEntry = {
  id: string;
  movie: Movie;
  watch_percentage: number;
  last_watched_at: string;
  completed_at: string | null;
};

export type WatchlistEntry = {
  id: string;
  movie: Movie;
  created_at: string;
};

export type Rating = {
  id: string;
  movie: string | Movie;
  score: string | number;
  created_at?: string;
  updated_at?: string;
};

export type SemanticSearchResponse = {
  query: string;
  count: number;
  results: Array<Movie & { score: number }>;
};

export type ApiErrorBody = {
  detail?: string;
  [key: string]: unknown;
};
