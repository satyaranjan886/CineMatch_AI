/** Central API configuration. */

const DIRECT_API_BASE =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") ?? "http://localhost:8000";

/**
 * Browser calls go through the Next.js rewrite (`/backend-api`) so the refresh
 * cookie is same-site. Server components can still hit the API directly.
 */
export const API_BASE_URL =
  typeof window === "undefined" ? DIRECT_API_BASE : "/backend-api";

export const API_PREFIX = "/api/v1";

export function apiUrl(path: string): string {
  const normalized = path.startsWith("/") ? path : `/${path}`;
  // Django routes use trailing slashes; always send them (before any query string).
  const [pathname, query = ""] = normalized.split("?", 2);
  const withSlash = pathname.endsWith("/") ? pathname : `${pathname}/`;
  return `${API_BASE_URL}${API_PREFIX}${withSlash}${query ? `?${query}` : ""}`;
}
