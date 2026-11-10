"use client";
import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { api } from "@/lib/api";

function ContenidoVerificacion() {
  const params = useSearchParams();
  const [estado, setEstado] = useState("Verificando tu correo…");
  useEffect(() => {
    const token = params.get("token");
    if (!token) { setEstado("El enlace de verificación está incompleto."); return; }
    api<{ email: string }>("/api/auth/verify-email", { method: "POST", body: JSON.stringify({ token }) })
      .then((r) => setEstado(`Correo verificado correctamente para ${r.email}. Ya puedes recibir tus resúmenes y recordatorios.`))
      .catch((e) => setEstado(e instanceof Error ? e.message : "No fue posible verificar el correo."));
  }, [params]);
  return <main className="hero-grid flex min-h-screen items-center justify-center px-5"><section className="surface-card w-full max-w-md p-8 text-center"><div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-teal/15 text-2xl text-teal">✓</div><h1 className="mt-4 text-xl font-bold">Verificación de correo</h1><p className="text-muted mt-3 text-sm leading-relaxed">{estado}</p><Link href="/iniciar-sesion" className="mt-6 inline-block text-sm font-semibold text-teal hover:underline">Ir a iniciar sesión</Link></section></main>;
}

export default function VerificarCorreo() {
  return <Suspense fallback={<main className="hero-grid flex min-h-screen items-center justify-center px-5"><p>Verificando tu correo…</p></main>}><ContenidoVerificacion /></Suspense>;
}
