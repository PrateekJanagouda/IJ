"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { api, post } from "./api";
import type { Me } from "./types";

type AuthState = {
  me: Me | null;
  loading: boolean;
  refresh: () => Promise<void>;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  hasRole: (role: "artist" | "organizer" | "moderator" | "administrator") => boolean;
};

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [me, setMe] = useState<Me | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      setMe(await api<Me>("/auth/me"));
    } catch {
      setMe(null); // 401 = signed out; the UI is still usable for public browsing
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const login = async (email: string, password: string) => {
    setMe(await post<Me>("/auth/login", { email, password }));
  };
  const logout = async () => {
    await post("/auth/logout");
    setMe(null);
  };
  const hasRole: AuthState["hasRole"] = (role) => !!me?.roles.includes(role);

  return (
    <AuthContext.Provider value={{ me, loading, refresh, login, logout, hasRole }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}
