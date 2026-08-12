"use client";

import { FormEvent, useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { RequireAuth } from "@/components/auth/require-auth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import * as authApi from "@/lib/api/auth";
import * as moviesApi from "@/lib/api/movies";
import { ApiError } from "@/lib/api/client";
import { useAuth } from "@/lib/auth/auth-context";

function SettingsContent() {
  const { profile, preferences, refreshMe } = useAuth();
  const [displayName, setDisplayName] = useState(profile?.display_name ?? "");
  const [languages, setLanguages] = useState((preferences?.preferred_languages ?? []).join(", "));
  const [decades, setDecades] = useState((preferences?.preferred_decades ?? []).join(", "));
  const [selectedGenres, setSelectedGenres] = useState<string[]>(preferences?.favorite_genre_ids ?? []);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  const genresQuery = useQuery({
    queryKey: ["genres"],
    queryFn: () => moviesApi.fetchGenres(),
  });

  useEffect(() => {
    setDisplayName(profile?.display_name ?? "");
    setLanguages((preferences?.preferred_languages ?? []).join(", "));
    setDecades((preferences?.preferred_decades ?? []).join(", "));
    setSelectedGenres(preferences?.favorite_genre_ids ?? []);
  }, [profile, preferences]);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setPending(true);
    setMessage(null);
    setError(null);
    try {
      await authApi.updateProfile({ display_name: displayName });
      await authApi.updatePreferences({
        preferred_languages: languages
          .split(",")
          .map((value) => value.trim())
          .filter(Boolean),
        preferred_decades: decades
          .split(",")
          .map((value) => Number(value.trim()))
          .filter((value) => !Number.isNaN(value)),
        favorite_genre_ids: selectedGenres,
      });
      await refreshMe();
      setMessage("Settings saved.");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to save settings.");
    } finally {
      setPending(false);
    }
  }

  function toggleGenre(id: string) {
    setSelectedGenres((current) =>
      current.includes(id) ? current.filter((value) => value !== id) : [...current, id],
    );
  }

  return (
    <div className="mx-auto max-w-2xl space-y-8 px-4 py-10 sm:px-6">
      <header>
        <h1 className="font-display text-4xl">Settings</h1>
        <p className="mt-2 text-muted-foreground">Tune your profile and taste preferences.</p>
      </header>

      <form className="space-y-6 rounded-xl border border-border/60 bg-card/40 p-6" onSubmit={onSubmit}>
        <div className="space-y-2">
          <label htmlFor="display-name" className="text-sm text-muted-foreground">
            Display name
          </label>
          <Input
            id="display-name"
            value={displayName}
            onChange={(event) => setDisplayName(event.target.value)}
          />
        </div>
        <div className="space-y-2">
          <label htmlFor="languages" className="text-sm text-muted-foreground">
            Preferred languages (comma-separated codes)
          </label>
          <Input
            id="languages"
            value={languages}
            onChange={(event) => setLanguages(event.target.value)}
            placeholder="en, fr, ja"
          />
        </div>
        <div className="space-y-2">
          <label htmlFor="decades" className="text-sm text-muted-foreground">
            Preferred decades (comma-separated)
          </label>
          <Input
            id="decades"
            value={decades}
            onChange={(event) => setDecades(event.target.value)}
            placeholder="1990, 2000, 2010"
          />
        </div>
        <fieldset>
          <legend className="text-sm text-muted-foreground">Favorite genres</legend>
          {genresQuery.isLoading ? <Skeleton className="mt-3 h-20 w-full" /> : null}
          <div className="mt-3 flex flex-wrap gap-2">
            {(genresQuery.data?.results ?? []).map((genre) => {
              const active = selectedGenres.includes(genre.id);
              return (
                <button
                  key={genre.id}
                  type="button"
                  aria-pressed={active}
                  onClick={() => toggleGenre(genre.id)}
                  className={
                    active
                      ? "rounded-full bg-primary px-3 py-1 text-xs font-medium text-primary-foreground"
                      : "rounded-full border border-border px-3 py-1 text-xs text-muted-foreground hover:bg-accent"
                  }
                >
                  {genre.name}
                </button>
              );
            })}
          </div>
        </fieldset>
        {message ? <p className="text-sm text-primary">{message}</p> : null}
        {error ? (
          <p role="alert" className="text-sm text-red-300">
            {error}
          </p>
        ) : null}
        <Button type="submit" disabled={pending}>
          {pending ? "Saving…" : "Save settings"}
        </Button>
      </form>
    </div>
  );
}

export default function SettingsPage() {
  return (
    <RequireAuth>
      <SettingsContent />
    </RequireAuth>
  );
}
