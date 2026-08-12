import type { Metadata } from "next";
import { Fraunces, Outfit } from "next/font/google";

import { AppShell } from "@/components/shell/app-shell";
import { AuthProvider } from "@/lib/auth/auth-context";
import { QueryProvider } from "@/lib/query-provider";

import "./globals.css";

const outfit = Outfit({
  variable: "--font-outfit",
  subsets: ["latin"],
});

const fraunces = Fraunces({
  variable: "--font-fraunces",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: {
    default: "CineMatch",
    template: "%s · CineMatch",
  },
  description: "Premium personalized movie discovery powered by hybrid AI recommendations.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className={`${outfit.variable} ${fraunces.variable} min-h-screen font-sans`}>
        <QueryProvider>
          <AuthProvider>
            <AppShell>{children}</AppShell>
          </AuthProvider>
        </QueryProvider>
      </body>
    </html>
  );
}
