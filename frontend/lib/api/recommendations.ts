import { apiRequest } from "@/lib/api/client";
import type {
  HomeRecommendationsResponse,
  RecommendationListResponse,
} from "@/types/api";

export function fetchPopular(limit = 20) {
  return apiRequest<RecommendationListResponse>("/recommendations/popular/", {
    auth: false,
    query: { limit },
  });
}

export function fetchTrending(limit = 20, window = 24) {
  return apiRequest<RecommendationListResponse>("/recommendations/trending/", {
    auth: false,
    query: { limit, window },
  });
}

export function fetchCollaborative(limit = 20) {
  return apiRequest<RecommendationListResponse>("/recommendations/collaborative/", {
    query: { limit },
  });
}

export function fetchHomeRecommendations(context?: string) {
  return apiRequest<HomeRecommendationsResponse>("/recommendations/home/", {
    query: context ? { context } : undefined,
  });
}
