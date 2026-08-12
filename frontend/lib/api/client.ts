import { apiUrl } from "@/lib/api/config";
import { clearTokens, getAccessToken, setAccessToken, setTokens } from "@/lib/auth/token-store";
import type { ApiErrorBody } from "@/types/api";

export class ApiError extends Error {
  status: number;
  body: ApiErrorBody;

  constructor(status: number, body: ApiErrorBody, message?: string) {
    super(message ?? body.detail ?? `Request failed (${status})`);
    this.name = "ApiError";
    this.status = status;
    this.body = body;
  }
}

type RequestOptions = {
  method?: string;
  body?: unknown;
  auth?: boolean;
  signal?: AbortSignal;
  query?: Record<string, string | number | boolean | undefined | null>;
  /** Internal: prevent infinite 401 → refresh → retry loops. */
  _retry?: boolean;
};

let refreshPromise: Promise<boolean> | null = null;

async function refreshAccessToken(): Promise<boolean> {
  const response = await fetch(apiUrl("/auth/refresh/"), {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
    body: JSON.stringify({}),
    credentials: "include",
    cache: "no-store",
  });

  if (!response.ok) {
    clearTokens();
    return false;
  }

  let data: { access?: string };
  try {
    data = (await response.json()) as { access?: string };
  } catch {
    clearTokens();
    return false;
  }
  if (!data.access) {
    clearTokens();
    return false;
  }
  setAccessToken(data.access);
  return true;
}

function buildUrl(path: string, query?: RequestOptions["query"]): string {
  const url = new URL(apiUrl(path), typeof window !== "undefined" ? window.location.origin : "http://localhost");
  if (query) {
    for (const [key, value] of Object.entries(query)) {
      if (value === undefined || value === null || value === "") continue;
      url.searchParams.set(key, String(value));
    }
  }
  return url.toString();
}

function parseBody(text: string): ApiErrorBody {
  if (!text) return {};
  try {
    return JSON.parse(text) as ApiErrorBody;
  } catch {
    return { detail: text.slice(0, 200) };
  }
}

export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const headers: Record<string, string> = {
    Accept: "application/json",
  };

  if (options.body !== undefined) {
    headers["Content-Type"] = "application/json";
  }

  const shouldAuth = options.auth !== false;
  const access = getAccessToken();
  if (shouldAuth && access) {
    headers.Authorization = `Bearer ${access}`;
  }

  const response = await fetch(buildUrl(path, options.query), {
    method: options.method ?? (options.body !== undefined ? "POST" : "GET"),
    headers,
    body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
    signal: options.signal,
    credentials: "include",
    cache: "no-store",
  });

  if (response.status === 401 && shouldAuth && !options._retry) {
    refreshPromise ??= refreshAccessToken().finally(() => {
      refreshPromise = null;
    });
    const refreshed = await refreshPromise;
    if (refreshed) {
      return apiRequest<T>(path, { ...options, auth: true, _retry: true });
    }
  }

  if (response.status === 204) {
    return undefined as T;
  }

  const text = await response.text();
  const body = parseBody(text);

  if (!response.ok) {
    throw new ApiError(response.status, body);
  }

  return body as T;
}

// Re-export for callers that still import setTokens from client paths.
export { setTokens };
