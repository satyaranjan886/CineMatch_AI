"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import * as authApi from "@/lib/api/auth";
import { ApiError } from "@/lib/api/client";
import { clearTokens, getAccessToken, setTokens } from "@/lib/auth/token-store";
import type { AuthUser, MeResponse, UserPreferences, UserProfile } from "@/types/api";

type AuthContextValue = {
  user: AuthUser | null;
  profile: UserProfile | null;
  preferences: UserPreferences | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (payload: {
    email: string;
    password: string;
    first_name?: string;
    last_name?: string;
    display_name?: string;
  }) => Promise<void>;
  logout: () => Promise<void>;
  refreshMe: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [preferences, setPreferences] = useState<UserPreferences | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const applyMe = useCallback((me: MeResponse) => {
    setUser(me.user);
    setProfile(me.profile);
    setPreferences(me.preferences);
  }, []);

  const refreshMe = useCallback(async () => {
    const me = await authApi.fetchMe();
    applyMe(me);
  }, [applyMe]);

  useEffect(() => {
    let cancelled = false;
    async function bootstrap() {
      try {
        // Access may be missing after reload; cookie refresh restores the session.
        if (!getAccessToken()) {
          const { apiRequest } = await import("@/lib/api/client");
          try {
            const tokens = await apiRequest<{ access: string }>("/auth/refresh/", {
              auth: false,
              method: "POST",
              body: {},
            });
            setTokens(tokens.access);
          } catch {
            if (!cancelled) setIsLoading(false);
            return;
          }
        }
        const me = await authApi.fetchMe();
        if (!cancelled) applyMe(me);
      } catch (error) {
        if (error instanceof ApiError && error.status === 401) {
          clearTokens();
        }
        if (!cancelled) {
          setUser(null);
          setProfile(null);
          setPreferences(null);
        }
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    }
    void bootstrap();
    return () => {
      cancelled = true;
    };
  }, [applyMe]);

  const login = useCallback(
    async (email: string, password: string) => {
      const tokens = await authApi.login(email, password);
      setTokens(tokens.access);
      await refreshMe();
    },
    [refreshMe],
  );

  const register = useCallback(
    async (payload: {
      email: string;
      password: string;
      first_name?: string;
      last_name?: string;
      display_name?: string;
    }) => {
      const response = await authApi.register(payload);
      setTokens(response.access);
      await refreshMe();
    },
    [refreshMe],
  );

  const logout = useCallback(async () => {
    try {
      await authApi.logout();
    } catch {
      // Ignore logout API errors; clear local session regardless.
    } finally {
      clearTokens();
      setUser(null);
      setProfile(null);
      setPreferences(null);
    }
  }, []);

  const value = useMemo(
    () => ({
      user,
      profile,
      preferences,
      isAuthenticated: Boolean(user),
      isLoading,
      login,
      register,
      logout,
      refreshMe,
    }),
    [user, profile, preferences, isLoading, login, register, logout, refreshMe],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return context;
}
