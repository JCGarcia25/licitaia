"use client";
/* Sesión de usuario y guarda de la app privada. */
import { createContext, ReactNode, useCallback, useContext, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, clearToken, getToken, setToken } from "@/lib/api";
import { Spinner } from "@/components/ui";

type User = { id: number; email: string; full_name: string };

type AuthContextValue = {
  user: User | null;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, fullName: string) => Promise<void>;
  logout: () => void;
};

// Next.js prerenders special routes such as /_not-found outside the normal
// client provider tree. Keep that render safe; regular app routes are still
// wrapped by AuthProvider in app/layout.tsx.
const fallbackAuth: AuthContextValue = {
  user: null,
  login: async () => { throw new Error("Autenticación no disponible"); },
  register: async () => { throw new Error("Autenticación no disponible"); },
  logout: () => undefined,
};

const AuthCtx = createContext<AuthContextValue>(fallbackAuth);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const router = useRouter();

  useEffect(() => {
    if (!getToken()) return;
    api<User>("/api/auth/me")
      .then(setUser)
      .catch(() => setUser(null));
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const form = new URLSearchParams({ username: email, password });
    const data = await api<{ access_token: string }>("/api/auth/login", { method: "POST", body: form.toString(), headers: { "Content-Type": "application/x-www-form-urlencoded" } });
    setToken(data.access_token);
    const me = await api<User>("/api/auth/me");
    setUser(me);
  }, []);

  const register = useCallback(async (email: string, password: string, fullName: string) => {
    const data = await api<{ access_token: string }>("/api/auth/register", {
      method: "POST",
      body: JSON.stringify({ email, password, full_name: fullName }),
    });
    setToken(data.access_token);
    const me = await api<User>("/api/auth/me");
    setUser(me);
  }, []);

  const logout = useCallback(() => {
    clearToken();
    setUser(null);
    router.push("/iniciar-sesion");
  }, [router]);

  return <AuthCtx.Provider value={{ user, login, register, logout }}>{children}</AuthCtx.Provider>;
}

export function useAuth() {
  return useContext(AuthCtx);
}

export function RequireAuth({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  const [checked, setChecked] = useState(false);
  const router = useRouter();

  useEffect(() => {
    const t = setTimeout(() => setChecked(true), 600);
    return () => clearTimeout(t);
  }, []);

  useEffect(() => {
    if (checked && !user) router.push("/iniciar-sesion");
  }, [checked, user, router]);

  if (!user) return <Spinner label="Verificando sesión…" />;
  return <>{children}</>;
}
