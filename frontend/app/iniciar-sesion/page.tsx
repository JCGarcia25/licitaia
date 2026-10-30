"use client";
import { FormEvent, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Button, Field, Input } from "@/components/ui";
import { useAuth } from "@/components/auth";

export default function IniciarSesion() {
  const { login } = useAuth();
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [cargando, setCargando] = useState(false);

  async function enviar(e: FormEvent) {
    e.preventDefault();
    setError("");
    setCargando(true);
    try {
      await login(email, password);
      router.push("/app");
    } catch (err) {
      setError(err instanceof Error ? err.message : "No fue posible iniciar sesión");
    } finally {
      setCargando(false);
    }
  }

  return (
      <div className="hero-grid flex min-h-screen items-center justify-center px-5">
      <div className="surface-card shadow-lift w-full max-w-md p-8">
        <Link href="/" className="mb-6 flex items-center gap-2">
          <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-900 font-bold text-white dark:bg-teal dark:text-slate-950">L</span>
          <span className="text-lg font-bold">MySECOP</span>
        </Link>
        <h1 className="text-xl font-bold tracking-tight">Iniciar sesión</h1>
        <p className="text-muted mt-1 text-sm">Accede a tu tablero de oportunidades.</p>
        <form onSubmit={enviar} className="mt-6 space-y-4">
          <Field label="Correo electrónico">
            <Input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} placeholder="tu@empresa.co" />
          </Field>
          <Field label="Contraseña">
            <Input type="password" required value={password} onChange={(e) => setPassword(e.target.value)} placeholder="••••••••" />
          </Field>
          {error ? <p className="text-xs text-red-600">{error}</p> : null}
          <Button type="submit" disabled={cargando} className="w-full">{cargando ? "Ingresando…" : "Ingresar"}</Button>
        </form>
        <p className="text-muted mt-5 text-xs">
          ¿No tienes cuenta? <Link href="/registro" className="text-teal font-medium hover:underline">Regístrate gratis</Link>
        </p>
        <p className="text-muted mt-3 rounded-lg border border-base bg-[var(--bg)] px-3 py-2 text-[11px]">
          Demostración: <code>demo@licitaia.co</code> / <code>LicitAIA2026</code> (datos de ejemplo con datos ilustrativos)
        </p>
      </div>
      </div>
  );
}
