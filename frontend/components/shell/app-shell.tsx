"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Menu, Search, X } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { useAuth } from "@/lib/auth/auth-context";
import { cn } from "@/lib/utils";

const NAV = [
  { href: "/home", label: "Home" },
  { href: "/movies", label: "Movies" },
  { href: "/search", label: "Search" },
  { href: "/watchlist", label: "Watchlist" },
  { href: "/history", label: "History" },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { isAuthenticated, profile, logout, isLoading, user } = useAuth();
  const [open, setOpen] = useState(false);
  const isAuthPage = pathname === "/login" || pathname === "/register";

  const navItems = [
    ...NAV,
    ...(user?.is_staff ? [{ href: "/admin", label: "Admin" }] : []),
  ];

  if (isAuthPage) {
    return <main className="min-h-screen">{children}</main>;
  }

  return (
    <div className="flex min-h-screen flex-col">
      <header className="sticky top-0 z-40 border-b border-border/50 bg-background/80 backdrop-blur-xl">
        <div className="mx-auto flex h-16 max-w-7xl items-center justify-between gap-4 px-4 sm:px-6 lg:px-8">
          <div className="flex items-center gap-6">
            <Link href="/" className="group flex items-center gap-2">
              <span className="font-display text-2xl tracking-tight text-champagne transition group-hover:text-primary">
                CineMatch
              </span>
              <span className="rounded-sm bg-primary/15 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-[0.2em] text-primary">
                AI
              </span>
            </Link>
            <nav className="hidden items-center gap-5 text-sm md:flex" aria-label="Primary">
              {navItems.map((item) => (
                <Link
                  key={item.href}
                  href={item.href}
                  className={cn(
                    "transition-colors hover:text-foreground",
                    pathname === item.href || pathname.startsWith(`${item.href}/`)
                      ? "text-foreground"
                      : "text-muted-foreground",
                  )}
                >
                  {item.label}
                </Link>
              ))}
            </nav>
          </div>

          <div className="flex items-center gap-2">
            <Button asChild variant="ghost" size="icon" className="md:hidden" aria-label="Search">
              <Link href="/search">
                <Search className="size-4" />
              </Link>
            </Button>
            {!isLoading && isAuthenticated ? (
              <>
                <Button asChild variant="ghost" size="sm" className="hidden sm:inline-flex">
                  <Link href="/profile">{profile?.display_name || "Profile"}</Link>
                </Button>
                <Button asChild variant="outline" size="sm" className="hidden sm:inline-flex">
                  <Link href="/settings">Settings</Link>
                </Button>
                <Button type="button" variant="ghost" size="sm" onClick={() => void logout()}>
                  Sign out
                </Button>
              </>
            ) : !isLoading ? (
              <>
                <Button asChild variant="ghost" size="sm">
                  <Link href="/login">Sign in</Link>
                </Button>
                <Button asChild size="sm">
                  <Link href="/register">Join</Link>
                </Button>
              </>
            ) : null}
            <Button
              type="button"
              variant="outline"
              size="icon"
              className="md:hidden"
              aria-expanded={open}
              aria-controls="mobile-nav"
              aria-label={open ? "Close menu" : "Open menu"}
              onClick={() => setOpen((value) => !value)}
            >
              {open ? <X className="size-4" /> : <Menu className="size-4" />}
            </Button>
          </div>
        </div>
        {open ? (
          <nav id="mobile-nav" className="border-t border-border/50 px-4 py-3 md:hidden" aria-label="Mobile">
            <ul className="space-y-2">
              {navItems.map((item) => (
                <li key={item.href}>
                  <Link
                    href={item.href}
                    className="block rounded-md px-2 py-2 text-sm text-foreground hover:bg-accent"
                    onClick={() => setOpen(false)}
                  >
                    {item.label}
                  </Link>
                </li>
              ))}
              <li>
                <Link href="/profile" className="block rounded-md px-2 py-2 text-sm" onClick={() => setOpen(false)}>
                  Profile
                </Link>
              </li>
              <li>
                <Link href="/settings" className="block rounded-md px-2 py-2 text-sm" onClick={() => setOpen(false)}>
                  Settings
                </Link>
              </li>
            </ul>
          </nav>
        ) : null}
      </header>
      <main className="flex-1">{children}</main>
      <footer className="border-t border-border/50 py-8 text-center text-sm text-muted-foreground">
        <p className="font-display text-base text-champagne/80">CineMatch</p>
        <p className="mt-1">Personalized movie discovery — curated for your taste.</p>
      </footer>
    </div>
  );
}
