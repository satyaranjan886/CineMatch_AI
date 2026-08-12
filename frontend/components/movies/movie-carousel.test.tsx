import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { MovieCarousel } from "@/components/movies/movie-carousel";

vi.mock("@/components/movies/movie-card", () => ({
  MovieCard: ({ movie }: { movie: { title: string } }) => <div>{movie.title}</div>,
}));

vi.mock("@/lib/auth/auth-context", () => ({
  useAuth: () => ({ isAuthenticated: false }),
}));

describe("MovieCarousel", () => {
  it("renders section heading and movies", () => {
    render(
      <MovieCarousel
        title="Trending Now"
        movies={[
          {
            id: "1",
            title: "Film A",
            original_title: "Film A",
            overview: "",
            tagline: "",
            release_date: null,
            release_year: 2020,
            runtime: null,
            language: "en",
            country: "",
            popularity: 1,
            vote_average: 7,
            vote_count: 10,
            poster_url: "",
            backdrop_url: "",
            status: "released",
            genres: [],
            created_at: "",
            updated_at: "",
          },
        ]}
      />,
    );
    expect(screen.getByRole("heading", { name: "Trending Now" })).toBeInTheDocument();
    expect(screen.getByText("Film A")).toBeInTheDocument();
  });

  it("shows loading skeleton state", () => {
    render(<MovieCarousel title="Loading Row" isLoading />);
    expect(screen.getByRole("status", { name: /loading movies/i })).toBeInTheDocument();
  });

  it("shows error state with retry", () => {
    const onRetry = vi.fn();
    render(<MovieCarousel title="Broken Row" isError onRetry={onRetry} />);
    expect(screen.getByRole("alert")).toBeInTheDocument();
    screen.getByRole("button", { name: /try again/i }).click();
    expect(onRetry).toHaveBeenCalled();
  });

  it("shows empty state when no movies", () => {
    render(<MovieCarousel title="Empty Row" movies={[]} emptyMessage="Come back later." />);
    expect(screen.getByText("Nothing here yet")).toBeInTheDocument();
    expect(screen.getByText("Come back later.")).toBeInTheDocument();
  });
});
