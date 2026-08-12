/** In-memory access token store. Refresh lives in an HttpOnly cookie. */

const LEGACY_ACCESS_KEY = "cinematch.access";
const LEGACY_REFRESH_KEY = "cinematch.refresh";

let accessToken: string | null = null;

function purgeLegacyStorage(): void {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(LEGACY_ACCESS_KEY);
  window.localStorage.removeItem(LEGACY_REFRESH_KEY);
  window.sessionStorage.removeItem(LEGACY_ACCESS_KEY);
  window.sessionStorage.removeItem(LEGACY_REFRESH_KEY);
}

purgeLegacyStorage();

export function getAccessToken(): string | null {
  return accessToken;
}

export function setAccessToken(access: string | null): void {
  accessToken = access;
  purgeLegacyStorage();
}

/** @deprecated Refresh tokens are HttpOnly cookies; kept for API compatibility. */
export function getRefreshToken(): string | null {
  return null;
}

export function setTokens(access: string, refresh?: string): void {
  void refresh;
  setAccessToken(access);
}

export function clearTokens(): void {
  accessToken = null;
  purgeLegacyStorage();
}
