import { apiRequest } from "@/lib/api/client";
import type {
  AuthResponse,
  HealthResponse,
  MeResponse,
  ReadinessResponse,
  UserPreferences,
  UserProfile,
} from "@/types/api";

export function fetchHealth() {
  return apiRequest<HealthResponse>("/health/", { auth: false });
}

export function fetchReadiness() {
  return apiRequest<ReadinessResponse>("/ready/", { auth: false });
}

export function login(email: string, password: string) {
  return apiRequest<AuthResponse>("/auth/login/", {
    auth: false,
    method: "POST",
    body: { email, password },
  });
}

export function register(payload: {
  email: string;
  password: string;
  first_name?: string;
  last_name?: string;
  display_name?: string;
}) {
  return apiRequest<AuthResponse>("/auth/register/", {
    auth: false,
    method: "POST",
    body: payload,
  });
}

export function logout() {
  return apiRequest<void>("/auth/logout/", {
    method: "POST",
    body: {},
  });
}

export function fetchMe() {
  return apiRequest<MeResponse>("/auth/me/");
}

export function updateProfile(payload: Partial<UserProfile>) {
  return apiRequest<UserProfile>("/auth/me/profile/", {
    method: "PATCH",
    body: payload,
  });
}

export function updatePreferences(payload: {
  preferred_languages?: string[];
  preferred_decades?: number[];
  favorite_genre_ids?: string[];
}) {
  return apiRequest<UserPreferences>("/auth/me/preferences/", {
    method: "PATCH",
    body: payload,
  });
}
