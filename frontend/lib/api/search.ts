import { apiRequest } from "@/lib/api/client";
import type { SemanticSearchResponse } from "@/types/api";

export function semanticSearch(query: string, limit = 20) {
  return apiRequest<SemanticSearchResponse>("/search/semantic/", {
    auth: false,
    query: { q: query, limit },
  });
}
