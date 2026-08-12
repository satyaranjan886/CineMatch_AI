import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { EmptyState, ErrorState } from "@/components/feedback/states";
import { CarouselSkeleton, MovieCardSkeleton, Skeleton } from "@/components/ui/skeleton";

describe("feedback and loading states", () => {
  it("renders empty state copy", () => {
    render(<EmptyState title="Nothing here" message="Add titles to get started." />);
    expect(screen.getByText("Nothing here")).toBeInTheDocument();
    expect(screen.getByText("Add titles to get started.")).toBeInTheDocument();
  });

  it("error state works without retry button", () => {
    render(<ErrorState title="Boom" message="Failed hard" />);
    expect(screen.getByRole("alert")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /try again/i })).not.toBeInTheDocument();
  });

  it("exposes loading skeletons for cards and carousels", () => {
    const { container } = render(
      <>
        <Skeleton data-testid="block" className="h-8 w-32" />
        <MovieCardSkeleton />
        <CarouselSkeleton count={3} />
      </>,
    );
    expect(screen.getByRole("status", { name: /loading movies/i })).toBeInTheDocument();
    expect(container.querySelectorAll('[data-slot="skeleton"], .animate-pulse').length).toBeGreaterThan(0);
  });
});
