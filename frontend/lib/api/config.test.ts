import { describe, expect, it } from "vitest";

import { apiUrl, API_BASE_URL } from "@/lib/api/config";

describe("api config", () => {
  it("builds versioned API urls", () => {
    expect(API_BASE_URL).toBeTruthy();
    expect(apiUrl("/movies/")).toContain("/api/v1/movies/");
  });

  it("always appends a trailing slash for Django", () => {
    expect(apiUrl("/auth/register")).toMatch(/\/api\/v1\/auth\/register\/$/);
    expect(apiUrl("/movies")).toMatch(/\/api\/v1\/movies\/$/);
  });
});
