import Link from "next/link";

import { Button } from "@/components/ui/button";

export default function LandingPage() {
  return (
    <div>
      <section className="relative min-h-[88vh] overflow-hidden">
        <div
          className="absolute inset-0 bg-[url('https://images.unsplash.com/photo-1489599849927-2ee91cede3ba?auto=format&fit=crop&w=2400&q=80')] bg-cover bg-center"
          role="img"
          aria-label="Cinema seats illuminated by a projected film"
        />
        <div className="absolute inset-0 bg-gradient-to-r from-background via-background/85 to-background/20" />
        <div className="absolute inset-0 film-grain opacity-40" />
        <div className="relative mx-auto flex min-h-[88vh] max-w-7xl flex-col justify-end px-4 pb-20 pt-28 sm:px-6 lg:px-8">
          <p className="mb-3 text-xs font-semibold uppercase tracking-[0.35em] text-primary">
            CineMatch
          </p>
          <h1 className="max-w-3xl font-display text-5xl leading-[0.95] tracking-tight text-foreground sm:text-6xl md:text-7xl">
            Films that find you.
          </h1>
          <p className="mt-5 max-w-xl text-base text-muted-foreground sm:text-lg">
            Hybrid recommendations blend your taste, similar viewers, and the pulse of what is rising
            now — so every night starts with a better match.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <Button asChild size="lg">
              <Link href="/register">Start discovering</Link>
            </Button>
            <Button asChild size="lg" variant="outline">
              <Link href="/movies">Browse the catalog</Link>
            </Button>
          </div>
        </div>
      </section>

      <section className="mx-auto grid max-w-7xl gap-10 px-4 py-20 sm:px-6 md:grid-cols-3 lg:px-8">
        {[
          {
            title: "Taste-aware",
            body: "Content, collaborative, and semantic signals rank titles around what you actually finish and love.",
          },
          {
            title: "Fresh without noise",
            body: "Trending and popularity stay in the mix, but diversity re-ranking keeps the shelf from feeling samey.",
          },
          {
            title: "Your private theater",
            body: "Continue watching, watchlists, and preference controls stay with your profile — never sold as spectacle.",
          },
        ].map((item) => (
          <div key={item.title}>
            <h2 className="font-display text-2xl text-champagne">{item.title}</h2>
            <p className="mt-3 text-sm leading-relaxed text-muted-foreground">{item.body}</p>
          </div>
        ))}
      </section>
    </div>
  );
}
