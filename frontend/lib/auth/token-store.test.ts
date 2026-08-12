import { describe, expect, it } from "vitest";

import { clearTokens, getAccessToken, getRefreshToken, setAccessToken, setTokens } from "@/lib/auth/token-store";

describe("token store", () => {
  it("keeps access tokens in memory only", () => {
    clearTokens();
    expect(getAccessToken()).toBeNull();
    expect(getRefreshToken()).toBeNull();

    setTokens("access-token-value", "refresh-should-be-ignored");
    expect(getAccessToken()).toBe("access-token-value");
    expect(getRefreshToken()).toBeNull();
    expect(window.localStorage.getItem("cinematch.access")).toBeNull();
    expect(window.localStorage.getItem("cinematch.refresh")).toBeNull();

    setAccessToken(null);
    expect(getAccessToken()).toBeNull();
  });

  it("purges legacy localStorage keys on clear", () => {
    window.localStorage.setItem("cinematch.access", "legacy");
    window.localStorage.setItem("cinematch.refresh", "legacy-refresh");
    clearTokens();
    expect(window.localStorage.getItem("cinematch.access")).toBeNull();
    expect(window.localStorage.getItem("cinematch.refresh")).toBeNull();
  });
});
