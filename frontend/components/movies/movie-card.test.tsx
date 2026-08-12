import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { describe, expect, it, vi } from "vitest";

import { MovieCard } from "@/components/movies/movie-card";
import type { Movie } from "@/types/api";

vi.mock("next/image", () => ({
  default: (props: { alt?: string; src?: string }) => (
    // eslint-disable-next-line @next/next/no-img-element
    <img alt={props.alt ?? ""} src={props.src} />
  ),
}));

vi.mock("next/link", () => ({
  default: ({ href, children, ...props }: { href: string; children: React.ReactNode }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}));

vi.mock("@/lib/auth/auth-context", () => ({
  useAuth: () => ({
    isAuthenticated: false,
    isLoading: false,
    user: null,
  }),
}));

const movie: Movie = {
  id: "11111111-1111-1111-1111-111111111111",
  title: "Interstellar",
  original_title: "Interstellar",
  overview: "Space exploration",
  tagline: "",
  release_date: "2014-11-07",
  release_year: 2014,
  runtime: 169,
  language: "en",
  country: "US",
  popularity: 90,
  vote_average: 8.6,
  vote_count: 1000,
  poster_url: "https://image.tmdb.org/t/p/w500/poster.jpg",
  backdrop_url: "",
  status: "released",
  genres: [{ id: "1", name: "Sci-Fi", slug: "sci-fi" }],
  created_at: "",
  updated_at: "",
};

function renderWithProviders(ui: React.ReactElement) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

describe("MovieCard", () => {
  it("renders title, year, rating, and genre", () => {
    renderWithProviders(<MovieCard movie={movie} />);
    expect(screen.getByText("Interstellar")).toBeInTheDocument();
    expect(screen.getByText("2014")).toBeInTheDocument();
    expect(screen.getByText("8.6")).toBeInTheDocument();
    expect(screen.getByText("Sci-Fi")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Interstellar/i })).toHaveAttribute(
      "href",
      "/movies/11111111-1111-1111-1111-111111111111",
    );
  });

  it("shows progress bar for partial watches", () => {
    const { container } = renderWithProviders(<MovieCard movie={movie} progress={40} />);
    const bar = container.querySelector("[aria-hidden='true']");
    expect(bar).toBeTruthy();
  });
});
