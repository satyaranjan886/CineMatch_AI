"use client";

import { useRef } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";

import { MovieCard } from "@/components/movies/movie-card";
import { Button } from "@/components/ui/button";
import { CarouselSkeleton } from "@/components/ui/skeleton";
import { EmptyState, ErrorState } from "@/components/feedback/states";
import type { Movie } from "@/types/api";

type MovieCarouselProps = {
  title: string;
  movies?: Movie[];
  isLoading?: boolean;
  isError?: boolean;
  onRetry?: () => void;
  progressByMovieId?: Record<string, number>;
  emptyMessage?: string;
};

export function MovieCarousel({
  title,
  movies = [],
  isLoading,
  isError,
  onRetry,
  progressByMovieId,
  emptyMessage = "No titles in this collection yet.",
}: MovieCarouselProps) {
  const scrollerRef = useRef<HTMLDivElement>(null);

  const scroll = (direction: "left" | "right") => {
    const node = scrollerRef.current;
    if (!node) return;
    const amount = Math.min(node.clientWidth * 0.85, 640);
    node.scrollBy({ left: direction === "left" ? -amount : amount, behavior: "smooth" });
  };

  return (
    <section className="space-y-3" aria-labelledby={`section-${slugify(title)}`}>
      <div className="flex items-end justify-between gap-3">
        <h2 id={`section-${slugify(title)}`} className="font-display text-2xl tracking-tight text-foreground md:text-3xl">
          {title}
        </h2>
        <div className="hidden gap-2 sm:flex">
          <Button
            type="button"
            size="icon"
            variant="outline"
            aria-label={`Scroll ${title} left`}
            onClick={() => scroll("left")}
          >
            <ChevronLeft />
          </Button>
          <Button
            type="button"
            size="icon"
            variant="outline"
            aria-label={`Scroll ${title} right`}
            onClick={() => scroll("right")}
          >
            <ChevronRight />
          </Button>
        </div>
      </div>

      {isLoading ? <CarouselSkeleton /> : null}
      {isError ? <ErrorState title={`Could not load ${title}`} onRetry={onRetry} /> : null}
      {!isLoading && !isError && movies.length === 0 ? (
        <EmptyState title="Nothing here yet" message={emptyMessage} />
      ) : null}
      {!isLoading && !isError && movies.length > 0 ? (
        <div
          ref={scrollerRef}
          className="scrollbar-hide flex gap-3 overflow-x-auto pb-2 scroll-smooth"
          tabIndex={0}
          role="list"
          aria-label={title}
        >
          {movies.map((movie) => (
            <div key={movie.id} role="listitem">
              <MovieCard
                movie={movie}
                progress={progressByMovieId?.[movie.id]}
                reason={movie.reason}
              />
            </div>
          ))}
        </div>
      ) : null}
    </section>
  );
}

function slugify(value: string) {
  return value.toLowerCase().replace(/[^a-z0-9]+/g, "-");
}
