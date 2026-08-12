import { apiRequest } from "@/lib/api/client";
import * as authApi from "@/lib/api/auth";
import * as interactionsApi from "@/lib/api/interactions";
import * as moviesApi from "@/lib/api/movies";
import * as recommendationsApi from "@/lib/api/recommendations";
import * as searchApi from "@/lib/api/search";
import { API_BASE_URL } from "@/lib/api/config";

export {
  API_BASE_URL,
  apiRequest,
  authApi,
  interactionsApi,
  moviesApi,
  recommendationsApi,
  searchApi,
};

/** @deprecated Prefer domain helpers under lib/api/* */
export { fetchHealth, fetchReadiness } from "@/lib/api/auth";
