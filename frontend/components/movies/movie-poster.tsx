"use client";

import Image from "next/image";

import { cn } from "@/lib/utils";

type MoviePosterProps = {
  src?: string | null;
  alt: string;
  className?: string;
  sizes?: string;
  priority?: boolean;
};

/** next/image with unoptimized so arbitrary poster hosts from the API work. */
export function MoviePoster({ src, alt, className, sizes, priority }: MoviePosterProps) {
  if (!src) {
    return <div className={cn("bg-muted", className)} aria-hidden={alt ? undefined : true} />;
  }

  return (
    <Image
      src={src}
      alt={alt}
      fill
      sizes={sizes}
      priority={priority}
      unoptimized
      className={cn("object-cover", className)}
    />
  );
}
