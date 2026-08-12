import { cn } from "@/lib/utils";

export function Skeleton({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      className={cn("animate-pulse rounded-md bg-muted/70", className)}
      aria-hidden="true"
      {...props}
    />
  );
}

export function MovieCardSkeleton() {
  return (
    <div className="w-[9.5rem] shrink-0 sm:w-40 md:w-44" aria-hidden="true">
      <Skeleton className="aspect-[2/3] w-full rounded-lg" />
      <Skeleton className="mt-2 h-4 w-4/5" />
      <Skeleton className="mt-1 h-3 w-1/2" />
    </div>
  );
}

export function CarouselSkeleton({ count = 6 }: { count?: number }) {
  return (
    <div className="flex gap-3 overflow-hidden" role="status" aria-label="Loading movies">
      {Array.from({ length: count }).map((_, index) => (
        <MovieCardSkeleton key={index} />
      ))}
    </div>
  );
}
