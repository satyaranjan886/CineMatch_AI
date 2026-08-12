import { apiRequest } from "@/lib/api/client";

export type AnalyticsDashboard = {
  as_of: string;
  computed_at: string;
  sufficient_data: boolean;
  metrics: {
    total_users: number;
    active_users: number;
    movies: number;
    interactions: number;
    interactions_today?: number;
    recommendations_served: number;
    recommendation_ctr: number | null;
    watch_completion: number | null;
    average_session_duration_seconds: number | null;
    cache_hit_rate: number | null;
  };
  recommendation: {
    recommendations_served: number;
    cache_hit_rate: number | null;
    recommendation_ctr: number | null;
    recommendation_conversion: number | null;
    by_algorithm: Array<{ algorithm: string; count: number }>;
    top_recommended_movies: Array<{ movie_id: string; title: string; count: number }>;
    top_clicked_recommendations: Array<{ movie_id: string; title: string; count: number }>;
    top_completed_recommendations: Array<{ movie_id: string; title: string; count: number }>;
  };
  users: {
    dau: number;
    wau: number;
    mau: number;
    new_users: number;
    returning_users: number;
    top_genres: Array<{ genre: string; count: number }>;
  };
  ml: {
    current_model_version: string | null;
    training_date: string | null;
    training_metrics: Record<string, unknown>;
    evaluation: {
      model_name?: string;
      model_version?: string;
      evaluated_at?: string;
      precision_at_k?: Record<string, number>;
      recall_at_k?: Record<string, number>;
      ndcg_at_k?: Record<string, number>;
      evaluated_users?: number;
    };
    latest_comparison_at?: string | null;
  };
  timeseries: Array<{
    date: string;
    dau: number | null;
    recommendations_served: number | null;
    recommendation_ctr: number | null;
    cache_hit_rate: number | null;
    interactions_today: number | null;
    new_users: number | null;
  }>;
  notes: string;
};

export function fetchAnalyticsDashboard(days = 14, refresh = false) {
  return apiRequest<AnalyticsDashboard>("/analytics/dashboard/", {
    query: { days, refresh: refresh ? "true" : undefined },
  });
}

export function refreshAnalyticsSnapshot() {
  return apiRequest<{ date: string; computed_at: string; status: string }>("/analytics/refresh/", {
    method: "POST",
    body: {},
  });
}
