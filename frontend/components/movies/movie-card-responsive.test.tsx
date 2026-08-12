import { render } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { MovieCard } from "@/components/movies/movie-card";

vi.mock("@/lib/auth/auth-context", () => ({
  useAuth: () => ({ isAuthenticated: false }),
}));

vi.mock("@tanstack/react-query", () => ({
  useMutation: () => ({ mutate: vi.fn(), isPending: false }),
  useQueryClient: () => ({ invalidateQueries: vi.fn() }),
}));

const movie = {
  id: "m1",
  title: "Responsive Film",
  original_title: "Responsive Film",
  overview: "",
  tagline: "",
  release_date: "2024-01-01",
  release_year: 2024,
  runtime: 120,
  language: "en",
  country: "",
  popularity: 1,
  vote_average: 8,
  vote_count: 10,
  poster_url: "",
  backdrop_url: "",
  status: "released",
  genres: [{ id: "g1", name: "Drama", slug: "drama" }],
  created_at: "",
  updated_at: "",
};

describe("MovieCard responsive layout", () => {
  it("uses responsive width classes for mobile and desktop", () => {
    const { container } = render(<MovieCard movie={movie} reason="Because you liked drama" />);
    const article = container.querySelector("article");
    expect(article?.className).toMatch(/w-\[9\.5rem\]/);
    expect(article?.className).toMatch(/sm:w-40/);
    expect(article?.className).toMatch(/md:w-44/);
  });
});
