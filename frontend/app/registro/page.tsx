"use client";
import { FormEvent, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Button, Field, Input } from "@/components/ui";
import { useAuth } from "@/components/auth";

export default function Registro() {
  const { register } = useAuth();
  const router = useRouter();
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [cargando, setCargando] = useState(false);

  async function enviar(e: FormEvent) {
    e.preventDefault();
    setError("");
    if (password.length < 8) {
      setError("La contraseña debe tener al menos 8 caracteres");
      return;
    }
    setCargando(true);
    try {
      await register(email, password, fullName);
      router.push("/app/perfil");
    } catch (err) {
      setError(err instanceof Error ? err.message : "No fue posible registrarse");
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
        <h1 className="text-xl font-bold tracking-tight">Crear cuenta gratuita</h1>
        <p className="text-muted mt-1 text-sm">Sin tarjeta de crédito. Incluye el plan Explorador.</p>
        <form onSubmit={enviar} className="mt-6 space-y-4">
          <Field label="Nombre y apellido">
            <Input required value={fullName} onChange={(e) => setFullName(e.target.value)} placeholder="Ana María Rojas" />
          </Field>
          <Field label="Correo corporativo">
            <Input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} placeholder="ana@tuempresa.co" />
          </Field>
          <Field label="Contraseña" hint="Mínimo 8 caracteres.">
            <Input type="password" required value={password} onChange={(e) => setPassword(e.target.value)} placeholder="••••••••" />
          </Field>
          {error ? <p className="text-xs text-red-600">{error}</p> : null}
          <Button type="submit" disabled={cargando} className="w-full">{cargando ? "Creando cuenta…" : "Comenzar gratis"}</Button>
        </form>
        <p className="text-muted mt-5 text-xs">
          ¿Ya tienes cuenta? <Link href="/iniciar-sesion" className="text-teal font-medium hover:underline">Inicia sesión</Link>
        </p>
        <p className="text-muted mt-4 text-[11px] leading-relaxed">
          Al registrarte aceptas los términos y la política de privacidad. LicitaIA no es una plataforma oficial del Gobierno colombiano.
        </p>
      </div>
      </div>
  );
}
